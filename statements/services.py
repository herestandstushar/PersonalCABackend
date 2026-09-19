"""
Statement ingestion: CSV/Excel/PDF → transactions.

PDF flow prefers bank-specific text parsers (ICICI, …) that also extract
bank/account metadata so we can auto-create the FinSight account when needed.
Generic table extraction remains as a fallback when an account is already chosen.
"""

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

import pandas as pd
from django.db import transaction as db_transaction

from statements.bank_parsers import detect_and_parse
from statements.models import Statement, StatementStatus, StatementMappingRule
from transactions.models import TransactionType, TransactionSource
from transactions.services import TransactionService


DATE_HEADERS = ["date", "txn date", "transaction date", "value date", "posted"]
DESCRIPTION_HEADERS = [
    "description", "narration", "particulars", "details", "remarks",
    "transaction details", "merchant", "payee",
]
AMOUNT_HEADERS = ["amount", "transaction amount", "amt", "value"]
DEBIT_HEADERS = ["debit", "withdrawal", "withdrawal amt", "dr", "money out", "paid out"]
CREDIT_HEADERS = ["credit", "deposit", "deposit amt", "cr", "money in", "paid in"]

DATE_FORMATS = [
    "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%m-%d-%Y",
    "%d/%m/%y", "%m/%d/%y", "%d-%b-%Y", "%d %b %Y", "%b %d, %Y",
    "%Y/%m/%d", "%d.%m.%Y",
]


class StatementParseError(Exception):
    """Raised when a statement cannot be interpreted well enough to import."""


class StatementParserService:
    @staticmethod
    def parse_and_import(statement_id, password: str = "", save_password: bool = True):
        statement = Statement.objects.select_related("account", "user").get(
            id=statement_id
        )
        statement.status = StatementStatus.PROCESSING
        statement.save(update_fields=["status"])

        used_password = password or ""

        try:
            name = (statement.filename or statement.file.name).lower()
            if name.endswith(".pdf"):
                imported, used_password = StatementParserService._import_smart_pdf(
                    statement, password=password, save_password=save_password
                )
            else:
                df = StatementParserService._read_file(statement, password=password)
                df.columns = [str(c).strip() for c in df.columns]
                if statement.account_id is None:
                    raise StatementParseError(
                        "Select an account for CSV/Excel imports."
                    )
                mapping = StatementParserService._resolve_mapping(df.columns.tolist())
                imported = StatementParserService._import_rows(statement, df, mapping)

            if imported == 0:
                raise StatementParseError(
                    "No transactions could be read from this file."
                )

            statement.status = StatementStatus.COMPLETED
            statement.transactions_imported = imported
            statement.error_message = ""
        except Exception as exc:
            statement.status = StatementStatus.FAILED
            message = str(exc)
            if StatementParserService._looks_like_password_error(message):
                message = (
                    "This PDF is password-protected. Enter the statement password "
                    "and try again."
                )
            statement.error_message = message[:500]

        statement.save(
            update_fields=[
                "status",
                "transactions_imported",
                "error_message",
                "account",
            ]
        )
        return statement.status == StatementStatus.COMPLETED

    # ---- smart PDF ----

    @staticmethod
    def _import_smart_pdf(statement, password: str = "", save_password: bool = True):
        text, tables, used_password = StatementParserService._extract_pdf_content(
            statement, password=password
        )
        if not text.strip():
            raise StatementParseError(
                "Could not read text from this PDF. Try exporting CSV from your bank."
            )

        try:
            parsed = detect_and_parse(text, tables=tables)
        except ValueError as exc:
            # Fall back to table extraction when an account was already chosen.
            if statement.account_id:
                df = StatementParserService._read_pdf(
                    statement.file.path, password=used_password
                )
                df.columns = [str(c).strip() for c in df.columns]
                mapping = StatementParserService._resolve_mapping(df.columns.tolist())
                return (
                    StatementParserService._import_rows(statement, df, mapping),
                    used_password,
                )
            raise StatementParseError(str(exc)) from exc

        # Prefer the account the user picked; otherwise detect/create from the PDF.
        if not statement.account_id:
            statement.account = StatementParserService.resolve_or_create_account(
                statement.user, parsed
            )
            statement.save(update_fields=["account"])

        if save_password and used_password and statement.account_id:
            from accounts.services import AccountService

            AccountService.set_statement_password(statement.account, used_password)

        imported = StatementParserService._import_parsed_txns(statement, parsed)
        return imported, used_password

    @staticmethod
    def _password_candidates(statement, password: str = "") -> list[str]:
        """Ordered unique passwords to try: provided → selected account → all saved."""
        from accounts.models import Account
        from accounts.services import AccountService

        candidates: list[str] = []
        if password:
            candidates.append(password)

        if statement.account_id and statement.account:
            saved = AccountService.get_statement_password(statement.account)
            if saved:
                candidates.append(saved)

        for acc in Account.objects.filter(user=statement.user, is_active=True):
            saved = AccountService.get_statement_password(acc)
            if saved:
                candidates.append(saved)

        candidates.append("")  # unencrypted PDFs
        # Preserve order, drop empties except the intentional trailing ""
        seen = set()
        ordered: list[str] = []
        for pw in candidates:
            key = pw  # empty string once at end is fine
            if key in seen and key != "":
                continue
            if key == "" and "" in seen:
                continue
            seen.add(key)
            ordered.append(pw)
        return ordered

    @staticmethod
    def _extract_pdf_content(statement, password: str = ""):
        try:
            import pdfplumber
        except ImportError as exc:
            raise StatementParseError(
                "PDF statements are not supported on this server."
            ) from exc

        path = statement.file.path
        last_error = None
        for candidate in StatementParserService._password_candidates(
            statement, password
        ):
            open_kwargs = {"password": candidate} if candidate else {}
            try:
                with pdfplumber.open(path, **open_kwargs) as pdf:
                    text = "\n".join(
                        (page.extract_text() or "") for page in pdf.pages
                    )
                    tables = []
                    for page in pdf.pages:
                        tables.extend(page.extract_tables() or [])
                return text, tables, candidate
            except Exception as exc:
                last_error = exc
                if StatementParserService._looks_like_password_error(str(exc)):
                    continue
                raise

        raise StatementParseError(
            "This PDF is password-protected. Enter the statement password "
            "and try again."
        ) from last_error

    @staticmethod
    def resolve_or_create_account(user, parsed):
        from accounts.models import Account, AccountType
        from accounts.services import AccountService
        from core.utils import decrypt_field
        from users.models import Currency

        meta = parsed.meta
        acct_no = (meta.account_number or "").strip()
        bank = (meta.bank_name or "Bank").strip()
        last4 = acct_no[-4:] if len(acct_no) >= 4 else acct_no

        # Match an existing account by full/last-4 number or bank + last4 in name.
        for acc in Account.objects.filter(user=user, is_active=True):
            if acct_no and acc.account_number_encrypted:
                try:
                    decrypted = decrypt_field(acc.account_number_encrypted)
                    if decrypted == acct_no or (
                        last4 and decrypted.endswith(last4)
                    ):
                        return acc
                except Exception:
                    pass
            if (
                bank
                and last4
                and bank.lower() in (acc.bank_name or acc.name or "").lower()
                and last4 in (acc.name or "")
            ):
                return acc

        currency = None
        if meta.currency_code:
            currency = Currency.objects.filter(code=meta.currency_code.upper()).first()
        if currency is None:
            currency = user.default_currency or Currency.objects.filter(code="INR").first()
        if currency is None:
            currency = Currency.objects.filter(code="USD").first()

        # Opening balance = balance before the first imported txn.
        opening = Decimal("0.00")
        if parsed.transactions:
            first = parsed.transactions[0]
            if first.txn_type == "expense":
                opening = first.balance + first.amount
            else:
                opening = first.balance - first.amount

        name = f"{bank} ····{last4}" if last4 else bank
        return AccountService.create_account(
            user,
            {
                "name": name[:200],
                "account_type": AccountType.BANK_ACCOUNT,
                "bank_name": bank[:200],
                "account_number": acct_no,
                "currency": currency,
                "current_balance": opening,
                "notes": f"Auto-created from statement import"
                + (f" ({meta.period_label})" if meta.period_label else ""),
            },
        )

    @staticmethod
    def _import_parsed_txns(statement, parsed) -> int:
        imported = 0
        with db_transaction.atomic():
            for txn in parsed.transactions:
                txn_type = (
                    TransactionType.INCOME
                    if txn.txn_type == "income"
                    else TransactionType.EXPENSE
                )
                TransactionService.create_transaction(
                    statement.user,
                    {
                        "account": statement.account,
                        "transaction_type": txn_type,
                        "amount": txn.amount,
                        "date": txn.date,
                        "description": txn.description,
                        "merchant_name": txn.merchant_name or txn.description[:100],
                        "source": TransactionSource.STATEMENT_IMPORT,
                        "statement_reference": (
                            f"stmt_{statement.id}_{parsed.parser_id}_{txn.serial}"
                        ),
                        "payment_method": "upi"
                        if "UPI" in txn.description.upper()[:8]
                        else "net_banking",
                    },
                )
                imported += 1
        return imported

    @staticmethod
    def _extract_pdf_text(path, password: str = "") -> str:
        text, _tables, _pw = StatementParserService._extract_pdf_content_path(
            path, password
        )
        return text

    @staticmethod
    def _extract_pdf_content_path(path, password: str = ""):
        try:
            import pdfplumber
        except ImportError as exc:
            raise StatementParseError(
                "PDF statements are not supported on this server."
            ) from exc

        open_kwargs = {"password": password} if password else {}
        try:
            with pdfplumber.open(path, **open_kwargs) as pdf:
                text = "\n".join((page.extract_text() or "") for page in pdf.pages)
                tables = []
                for page in pdf.pages:
                    tables.extend(page.extract_tables() or [])
            return text, tables, password
        except Exception as exc:
            if StatementParserService._looks_like_password_error(str(exc)):
                raise StatementParseError(
                    "This PDF is password-protected. Enter the statement password "
                    "and try again."
                ) from exc
            raise

    # ---- reading helpers ----

    @staticmethod
    def _looks_like_password_error(message: str) -> bool:
        lowered = message.lower()
        needles = (
            "password",
            "encrypted",
            "decrypt",
            "file has not been decrypted",
            "incorrect password",
        )
        return any(n in lowered for n in needles)

    @staticmethod
    def _read_file(statement, password: str = ""):
        name = (statement.filename or statement.file.name).lower()
        path = statement.file.path

        if name.endswith((".xlsx", ".xls")):
            return pd.read_excel(path)
        if name.endswith(".pdf"):
            return StatementParserService._read_pdf(path, password=password)
        for encoding in ("utf-8", "utf-8-sig", "latin-1"):
            try:
                return pd.read_csv(path, encoding=encoding)
            except UnicodeDecodeError:
                continue
        raise StatementParseError(
            "Could not decode the file; try exporting it as UTF-8 CSV."
        )

    @staticmethod
    def _read_pdf(path, password: str = ""):
        try:
            import pdfplumber
        except ImportError:
            raise StatementParseError(
                "PDF statements are not supported on this server. Export as CSV instead."
            )

        open_kwargs = {"password": password} if password else {}
        try:
            pdf_ctx = pdfplumber.open(path, **open_kwargs)
        except Exception as exc:
            if StatementParserService._looks_like_password_error(str(exc)):
                raise StatementParseError(
                    "This PDF is password-protected. Enter the statement password "
                    "and try again."
                ) from exc
            raise

        rows, header = [], None
        with pdf_ctx as pdf:
            for page in pdf.pages:
                for table in page.extract_tables() or []:
                    if not table:
                        continue
                    if header is None:
                        header = [str(c or "").strip() for c in table[0]]
                        body = table[1:]
                    else:
                        body = table
                    for row in body:
                        if row and len(row) == len(header):
                            rows.append([str(c or "").strip() for c in row])

        if not header or not rows:
            raise StatementParseError(
                "No table could be extracted from this PDF. Export as CSV instead."
            )
        return pd.DataFrame(rows, columns=header)

    # ---- column mapping ----

    @staticmethod
    def _resolve_mapping(columns):
        rule = StatementParserService._find_best_mapping_rule(columns)
        if rule:
            return {
                "date": rule.date_column,
                "description": rule.description_column,
                "amount": rule.amount_column or None,
                "debit": rule.debit_column or None,
                "credit": rule.credit_column or None,
                "date_format": rule.date_format,
            }

        mapping = {
            "date": StatementParserService._match_column(columns, DATE_HEADERS),
            "description": StatementParserService._match_column(
                columns, DESCRIPTION_HEADERS
            ),
            "amount": StatementParserService._match_column(columns, AMOUNT_HEADERS),
            "debit": StatementParserService._match_column(columns, DEBIT_HEADERS),
            "credit": StatementParserService._match_column(columns, CREDIT_HEADERS),
            "date_format": None,
        }

        if not mapping["date"] or not mapping["description"]:
            raise StatementParseError(
                "Could not find date and description columns. Found: "
                + ", ".join(columns[:10])
            )
        if not mapping["amount"] and not (mapping["debit"] or mapping["credit"]):
            raise StatementParseError(
                "Could not find an amount (or debit/credit) column. Found: "
                + ", ".join(columns[:10])
            )
        return mapping

    @staticmethod
    def _match_column(columns, candidates):
        normalised = {re.sub(r"[^a-z0-9]", "", c.lower()): c for c in columns}
        for candidate in candidates:
            key = re.sub(r"[^a-z0-9]", "", candidate.lower())
            if key in normalised:
                return normalised[key]
        for candidate in candidates:
            key = re.sub(r"[^a-z0-9]", "", candidate.lower())
            for norm, original in normalised.items():
                if key and key in norm:
                    return original
        return None

    @staticmethod
    def _find_best_mapping_rule(columns):
        for rule in StatementMappingRule.objects.filter(is_global=True):
            required = [rule.date_column, rule.description_column]
            if rule.amount_column:
                required.append(rule.amount_column)
            else:
                required.extend([rule.debit_column, rule.credit_column])
            if all(col and col in columns for col in required):
                return rule
        return None

    # ---- row import (generic tables) ----

    @staticmethod
    def _import_rows(statement, df, mapping):
        imported = 0
        with db_transaction.atomic():
            for index, row in df.iterrows():
                parsed = StatementParserService._parse_row(row, mapping)
                if not parsed:
                    continue
                txn_date, description, amount, txn_type = parsed
                TransactionService.create_transaction(
                    statement.user,
                    {
                        "account": statement.account,
                        "transaction_type": txn_type,
                        "amount": amount,
                        "date": txn_date,
                        "description": description,
                        "merchant_name": description[:100],
                        "source": TransactionSource.STATEMENT_IMPORT,
                        "statement_reference": f"stmt_{statement.id}_row_{index}",
                    },
                )
                imported += 1
        return imported

    @staticmethod
    def _parse_row(row, mapping):
        raw_date = row.get(mapping["date"])
        if pd.isna(raw_date):
            return None

        txn_date = StatementParserService._parse_date(raw_date, mapping["date_format"])
        if not txn_date:
            return None

        description = str(row.get(mapping["description"], "")).strip()
        if not description or description.lower() == "nan":
            description = "Imported transaction"

        amount, txn_type = StatementParserService._parse_amount(row, mapping)
        if amount is None or amount == 0:
            return None

        return txn_date, description, amount, txn_type

    @staticmethod
    def _parse_date(value, explicit_format):
        if isinstance(value, datetime):
            return value.date()
        if hasattr(value, "to_pydatetime"):
            return value.to_pydatetime().date()

        raw = str(value).strip()
        formats = [explicit_format] if explicit_format else []
        formats += DATE_FORMATS
        for fmt in formats:
            if not fmt:
                continue
            try:
                return datetime.strptime(raw, fmt).date()
            except ValueError:
                continue
        return None

    @staticmethod
    def _to_decimal(value):
        if value is None or pd.isna(value):
            return None
        raw = re.sub(r"[^\d.\-]", "", str(value).strip())
        if not raw or raw in {"-", "."}:
            return None
        try:
            return Decimal(raw)
        except InvalidOperation:
            return None

    @staticmethod
    def _parse_amount(row, mapping):
        if mapping["debit"] or mapping["credit"]:
            debit = (
                StatementParserService._to_decimal(row.get(mapping["debit"]))
                if mapping["debit"]
                else None
            )
            credit = (
                StatementParserService._to_decimal(row.get(mapping["credit"]))
                if mapping["credit"]
                else None
            )
            if debit:
                return abs(debit), TransactionType.EXPENSE
            if credit:
                return abs(credit), TransactionType.INCOME
            if not mapping["amount"]:
                return None, None

        amount = StatementParserService._to_decimal(row.get(mapping["amount"]))
        if amount is None:
            return None, None
        if amount > 0:
            return amount, TransactionType.INCOME
        return abs(amount), TransactionType.EXPENSE
