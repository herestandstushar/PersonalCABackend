"""
Bank-specific PDF statement parsers.

ICICI (JasperReports) puts transactions in the text layer.
HDFC exposes proper tables (Withdrawal / Deposit / Closing Balance).
Both extract bank + account metadata for smart auto-create.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional


@dataclass
class StatementMeta:
    bank_name: str = ""
    account_number: str = ""
    currency_code: str = "INR"
    account_type_hint: str = "bank_account"
    period_label: str = ""


@dataclass
class ParsedTxn:
    serial: int
    date: datetime.date
    amount: Decimal
    balance: Decimal
    txn_type: str  # expense | income
    description: str
    merchant_name: str = ""


@dataclass
class ParsedStatement:
    meta: StatementMeta
    transactions: list[ParsedTxn] = field(default_factory=list)
    parser_id: str = ""


def _to_decimal(raw: str) -> Optional[Decimal]:
    try:
        return Decimal(re.sub(r"[^\d.]", "", str(raw)))
    except (InvalidOperation, TypeError):
        return None


# ---------------------------------------------------------------------------
# ICICI
# ---------------------------------------------------------------------------

# SNo  DD.MM.YYYY  amount  [optional second amount]  balance
TXN_LINE = re.compile(
    r"^(\d+)\s+(\d{2}\.\d{2}\.\d{4})\s+([\d,]+\.\d{2})"
    r"(?:\s+([\d,]+\.\d{2}))?\s+([\d,]+\.\d{2})\s*$"
)


class IciciStatementParser:
    """ICICI Bank savings / current account PDF (JasperReports layout)."""

    id = "icici"

    @classmethod
    def matches(cls, text: str) -> bool:
        upper = text.upper()
        return "ICICI BANK" in upper and (
            "STATEMENT OF TRANSACTIONS" in upper
            or "TRANSACTION REMARKS" in upper
            or "WITHDRAWAL" in upper
        )

    @classmethod
    def parse(cls, text: str) -> ParsedStatement:
        meta = cls._extract_meta(text)
        rows = cls._extract_txn_rows(text)
        if not rows:
            raise ValueError("No ICICI transactions found in this PDF.")

        txns = cls._infer_directions(rows)
        return ParsedStatement(meta=meta, transactions=txns, parser_id=cls.id)

    @classmethod
    def _extract_meta(cls, text: str) -> StatementMeta:
        meta = StatementMeta(bank_name="ICICI Bank")

        m = re.search(
            r"(?:Saving|Savings|Current)\s+Account\s+no\.\s*(\d+)",
            text,
            re.I,
        )
        if not m:
            m = re.search(r"Account\s+no\.\s*(\d+)", text, re.I)
        if m:
            meta.account_number = m.group(1)

        m = re.search(r"\bin\s+([A-Z]{3})\s+for the period", text)
        if m:
            meta.currency_code = m.group(1)

        m = re.search(r"for the period\s+(.+?)(?:\n|$)", text, re.I)
        if m:
            meta.period_label = m.group(1).strip()

        return meta

    @classmethod
    def _extract_txn_rows(cls, text: str) -> list[dict]:
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        rows: list[dict] = []

        for i, line in enumerate(lines):
            m = TXN_LINE.match(line)
            if not m:
                continue
            sno, date_s, amt_a, amt_b, bal_s = m.groups()
            amount = _to_decimal(amt_a)
            second = _to_decimal(amt_b) if amt_b else None
            balance = _to_decimal(bal_s)
            if amount is None or balance is None:
                continue

            remark_parts: list[str] = []
            if i > 0 and not TXN_LINE.match(lines[i - 1]):
                prev = lines[i - 1]
                if not re.search(
                    r"S No\.|Withdrawal|Deposit|Balance|Statement of", prev, re.I
                ):
                    if len(prev) < 80:
                        remark_parts.append(prev)

            for j in range(i + 1, min(i + 6, len(lines))):
                nxt = lines[j]
                if TXN_LINE.match(nxt):
                    break
                if re.match(r"^\d+$", nxt):
                    break
                remark_parts.append(nxt)

            description = re.sub(r"\s+", " ", " ".join(remark_parts).strip())

            rows.append(
                {
                    "serial": int(sno),
                    "date": datetime.strptime(date_s, "%d.%m.%Y").date(),
                    "amount_a": amount,
                    "amount_b": second,
                    "balance": balance,
                    "description": description or "ICICI transaction",
                }
            )

        rows.sort(key=lambda r: (r["serial"], r["date"]))
        return rows

    @classmethod
    def _infer_directions(cls, rows: list[dict]) -> list[ParsedTxn]:
        txns: list[ParsedTxn] = []
        prev_balance: Optional[Decimal] = None

        for row in rows:
            amount = row["amount_a"]
            balance = row["balance"]
            second = row["amount_b"]
            desc = row["description"]
            desc_l = desc.lower()

            txn_type = None
            final_amount = amount

            if second is not None and second > 0 and amount > 0:
                if prev_balance is not None:
                    if abs((prev_balance - amount) - balance) < Decimal("0.05"):
                        txn_type, final_amount = "expense", amount
                    elif abs((prev_balance + second) - balance) < Decimal("0.05"):
                        txn_type, final_amount = "income", second
                if txn_type is None:
                    txn_type, final_amount = "expense", amount
            elif prev_balance is not None:
                if abs((prev_balance - amount) - balance) < Decimal("0.05"):
                    txn_type = "expense"
                elif abs((prev_balance + amount) - balance) < Decimal("0.05"):
                    txn_type = "income"

            if txn_type is None:
                if any(
                    k in desc_l
                    for k in (
                        "neft",
                        "rtgs",
                        "imps",
                        "int.pd",
                        "interest",
                        "salary",
                        "credit trxn",
                        "upi/cr",
                    )
                ):
                    txn_type = "income"
                else:
                    txn_type = "expense"

            merchant = (
                desc.split("/")[1]
                if desc.upper().startswith("UPI/") and "/" in desc[4:]
                else desc[:80]
            )

            txns.append(
                ParsedTxn(
                    serial=row["serial"],
                    date=row["date"],
                    amount=final_amount,
                    balance=balance,
                    txn_type=txn_type,
                    description=desc[:500],
                    merchant_name=(merchant or "ICICI")[:100],
                )
            )
            prev_balance = balance

        return txns


# ---------------------------------------------------------------------------
# HDFC
# ---------------------------------------------------------------------------

_HDFC_DATE = re.compile(r"^(\d{2}/\d{2}/\d{4})$")
_HDFC_MONEY = re.compile(r"^[\d,]+\.\d{2}$")


class HdfcStatementParser:
    """HDFC Bank account statement PDF (tabular Withdrawal/Deposit layout)."""

    id = "hdfc"

    @classmethod
    def matches(cls, text: str) -> bool:
        upper = text.upper()
        return (
            "HDFC BANK" in upper
            or "RTGS/NEFT IFSC : HDFC" in upper
            or ("ACCOUNT NUMBER" in upper and "HDFC" in upper)
        )

    @classmethod
    def parse(cls, text: str) -> ParsedStatement:
        return cls.parse_with_tables(text, tables=None)

    @classmethod
    def parse_with_tables(cls, text: str, tables=None) -> ParsedStatement:
        meta = cls._extract_meta(text)
        txns: list[ParsedTxn] = []
        if tables:
            txns = cls._txns_from_tables(tables)
        if not txns:
            txns = cls._txns_from_text(text)
        if not txns:
            raise ValueError("No HDFC transactions found in this PDF.")
        return ParsedStatement(meta=meta, transactions=txns, parser_id=cls.id)

    @classmethod
    def _extract_meta(cls, text: str) -> StatementMeta:
        meta = StatementMeta(bank_name="HDFC Bank")

        m = re.search(r"Account\s+number\s*:\s*(\d+)", text, re.I)
        if m:
            meta.account_number = m.group(1)

        m = re.search(r"Currency\s*:\s*([A-Z]{3})", text, re.I)
        if m:
            meta.currency_code = m.group(1).upper()

        m = re.search(
            r"Statement\s+From\s*:\s*([^\n]+?)(?:\n|$)",
            text,
            re.I,
        )
        if m:
            meta.period_label = re.sub(r"\s+", " ", m.group(1).strip())

        return meta

    @classmethod
    def _txns_from_tables(cls, tables) -> list[ParsedTxn]:
        txns: list[ParsedTxn] = []
        serial = 0

        for table in tables or []:
            if not table:
                continue
            header_idx = None
            colmap: dict[str, int] = {}

            for i, row in enumerate(table):
                cells = [str(c or "").strip() for c in row]
                joined = " ".join(cells).lower()
                if (
                    "date" in joined
                    and ("withdrawal" in joined or "deposit" in joined)
                    and "balance" in joined
                ):
                    header_idx = i
                    for j, cell in enumerate(cells):
                        key = re.sub(r"[^a-z]", "", cell.lower())
                        if key.startswith("date") and "date" not in colmap:
                            colmap["date"] = j
                        elif "narration" in key or "particular" in key:
                            colmap["narration"] = j
                        elif "withdrawal" in key:
                            colmap["withdrawal"] = j
                        elif "deposit" in key:
                            colmap["deposit"] = j
                        elif "closingbalance" in key or key == "balance":
                            colmap["balance"] = j
                    break

            if header_idx is None or "date" not in colmap or "balance" not in colmap:
                # Some continuation pages omit the header — treat as data rows
                # if cells look like HDFC txn rows.
                body = table
                assumed = {
                    "date": 0,
                    "narration": 1,
                    "withdrawal": 4,
                    "deposit": 5,
                    "balance": 6,
                }
                for row in body:
                    parsed = cls._row_from_cells(row, assumed, serial + 1)
                    if parsed:
                        serial += 1
                        parsed.serial = serial
                        txns.append(parsed)
                continue

            for row in table[header_idx + 1 :]:
                parsed = cls._row_from_cells(row, colmap, serial + 1)
                if parsed:
                    serial += 1
                    parsed.serial = serial
                    txns.append(parsed)

        return txns

    @classmethod
    def _row_from_cells(cls, row, colmap: dict, serial: int) -> Optional[ParsedTxn]:
        cells = [str(c or "").strip() for c in (row or [])]
        if not cells or len(cells) < 4:
            return None

        try:
            date_raw = cells[colmap["date"]]
        except (KeyError, IndexError):
            return None

        # Multi-line cell may start with narration residue — take first date-like token
        date_m = re.search(r"(\d{2}/\d{2}/\d{4})", date_raw)
        if not date_m:
            return None
        try:
            txn_date = datetime.strptime(date_m.group(1), "%d/%m/%Y").date()
        except ValueError:
            return None

        narration = ""
        if "narration" in colmap and colmap["narration"] < len(cells):
            narration = re.sub(r"\s+", " ", cells[colmap["narration"]].replace("\n", " "))

        withdrawal = Decimal("0")
        deposit = Decimal("0")
        if "withdrawal" in colmap and colmap["withdrawal"] < len(cells):
            withdrawal = _to_decimal(cells[colmap["withdrawal"]]) or Decimal("0")
        if "deposit" in colmap and colmap["deposit"] < len(cells):
            deposit = _to_decimal(cells[colmap["deposit"]]) or Decimal("0")

        try:
            balance = _to_decimal(cells[colmap["balance"]])
        except (KeyError, IndexError):
            balance = None
        if balance is None:
            return None

        if withdrawal > 0 and deposit == 0:
            txn_type, amount = "expense", withdrawal
        elif deposit > 0 and withdrawal == 0:
            txn_type, amount = "income", deposit
        elif withdrawal > 0:
            txn_type, amount = "expense", withdrawal
        elif deposit > 0:
            txn_type, amount = "income", deposit
        else:
            return None

        desc = narration or "HDFC transaction"
        merchant = cls._merchant_from_narration(desc)

        return ParsedTxn(
            serial=serial,
            date=txn_date,
            amount=amount,
            balance=balance,
            txn_type=txn_type,
            description=desc[:500],
            merchant_name=merchant[:100],
        )

    @classmethod
    def _merchant_from_narration(cls, desc: str) -> str:
        upper = desc.upper()
        if upper.startswith("UPI-"):
            # UPI-MERCHANT NAME-vpa@bank-...
            parts = desc.split("-")
            if len(parts) >= 2:
                return parts[1].strip()[:80] or desc[:80]
        return desc[:80]

    @classmethod
    def _txns_from_text(cls, text: str) -> list[ParsedTxn]:
        """Fallback when table extraction fails — parse numeric txn lines."""
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        txns: list[ParsedTxn] = []
        serial = 0
        # DD/MM/YYYY  ref  DD/MM/YYYY  withdrawal  deposit  balance
        pattern = re.compile(
            r"^(\d{2}/\d{2}/\d{4})\s+(\S+)\s+(\d{2}/\d{2}/\d{4})\s+"
            r"([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})$"
        )

        for i, line in enumerate(lines):
            # Some lines bury the amounts after a long narration fragment
            m = pattern.search(line)
            if not m:
                # Try trailing money triple
                m2 = re.search(
                    r"(\d{2}/\d{2}/\d{4})\s+.*?([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s*$",
                    line,
                )
                if not m2:
                    continue
                date_s, w_s, d_s, bal_s = m2.group(1), m2.group(2), m2.group(3), m2.group(4)
            else:
                date_s, _ref, _vd, w_s, d_s, bal_s = m.groups()

            withdrawal = _to_decimal(w_s) or Decimal("0")
            deposit = _to_decimal(d_s) or Decimal("0")
            balance = _to_decimal(bal_s)
            if balance is None:
                continue
            if withdrawal == 0 and deposit == 0:
                continue

            # Narration often sits on the previous line(s)
            desc_parts: list[str] = []
            if i > 0 and not pattern.search(lines[i - 1]):
                prev = lines[i - 1]
                if not re.search(
                    r"Statement From|Opening Balance|Page \d|Account Branch",
                    prev,
                    re.I,
                ):
                    desc_parts.append(prev)
            for j in range(i + 1, min(i + 3, len(lines))):
                nxt = lines[j]
                if pattern.search(nxt) or re.match(r"^\d{2}/\d{2}/\d{4}", nxt):
                    break
                if re.search(r"STATEMENT SUMMARY|END OF STATEMENT|Generation Date", nxt, re.I):
                    break
                desc_parts.append(nxt)

            desc = re.sub(r"\s+", " ", " ".join(desc_parts)).strip() or "HDFC transaction"
            if withdrawal > 0:
                txn_type, amount = "expense", withdrawal
            else:
                txn_type, amount = "income", deposit

            serial += 1
            txns.append(
                ParsedTxn(
                    serial=serial,
                    date=datetime.strptime(date_s, "%d/%m/%Y").date(),
                    amount=amount,
                    balance=balance,
                    txn_type=txn_type,
                    description=desc[:500],
                    merchant_name=cls._merchant_from_narration(desc)[:100],
                )
            )

        return txns


PARSERS = [IciciStatementParser, HdfcStatementParser]

SUPPORTED_BANKS = "ICICI Bank, HDFC Bank"


def detect_and_parse(text: str, tables=None) -> ParsedStatement:
    for parser in PARSERS:
        if parser.matches(text):
            if tables is not None and hasattr(parser, "parse_with_tables"):
                return parser.parse_with_tables(text, tables)
            return parser.parse(text)
    raise ValueError(
        f"Unrecognized bank statement format. Supported today: {SUPPORTED_BANKS}. "
        "Try exporting CSV from your bank, or pick an account manually for generic PDFs."
    )
