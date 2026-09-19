"""
Statement ingestion: reads CSV/Excel/PDF exports and turns rows into
transactions.

Banks rarely agree on column names, so parsing runs in two stages: an explicit
`StatementMappingRule` is used when one matches the file's headers, and
otherwise the columns are inferred from common header keywords. That keeps
imports working for banks nobody has configured a template for.
"""

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

import pandas as pd
from django.db import transaction as db_transaction

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
    def parse_and_import(statement_id, password: str = ""):
        statement = Statement.objects.get(id=statement_id)
        statement.status = StatementStatus.PROCESSING
        statement.save(update_fields=["status"])

        try:
            df = StatementParserService._read_file(statement, password=password)
            df.columns = [str(c).strip() for c in df.columns]

            mapping = StatementParserService._resolve_mapping(df.columns.tolist())
            imported = StatementParserService._import_rows(statement, df, mapping)

            if imported == 0:
                raise StatementParseError(
                    "No transactions could be read from this file. Check that it "
                    "contains date, description and amount columns."
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
            update_fields=["status", "transactions_imported", "error_message"]
        )
        return statement.status == StatementStatus.COMPLETED

    # ---- reading ----

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
        # Tolerate the stray encodings banks emit for CSV exports.
        for encoding in ("utf-8", "utf-8-sig", "latin-1"):
            try:
                return pd.read_csv(path, encoding=encoding)
            except UnicodeDecodeError:
                continue
        raise StatementParseError("Could not decode the file; try exporting it as UTF-8 CSV.")

    @staticmethod
    def _read_pdf(path, password: str = ""):
        try:
            import pdfplumber
        except ImportError:
            raise StatementParseError(
                "PDF statements are not supported on this server. Export as CSV instead."
            )

        open_kwargs = {}
        if password:
            open_kwargs["password"] = password

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
            "description": StatementParserService._match_column(columns, DESCRIPTION_HEADERS),
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

    # ---- row import ----

    @staticmethod
    def _import_rows(statement, df, mapping):
        imported = 0
        with db_transaction.atomic():
            for index, row in df.iterrows():
                parsed = StatementParserService._parse_row(row, mapping)
                if not parsed:
                    continue
                txn_date, description, amount, txn_type = parsed

                # Category is left out on purpose: TransactionService
                # auto-categorises from the merchant and description.
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
        """Returns (date, description, amount, type), or None for rows to skip."""
        raw_date = row.get(mapping["date"])
        if pd.isna(raw_date):
            return None

        txn_date = StatementParserService._parse_date(raw_date, mapping["date_format"])
        if not txn_date:
            # Blank lines, subtotals and footers all fail here; skipping them is
            # expected rather than an error.
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
        # A single amount column encodes direction by sign.
        if amount > 0:
            return amount, TransactionType.INCOME
        return abs(amount), TransactionType.EXPENSE
