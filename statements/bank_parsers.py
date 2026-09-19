"""
Bank-specific PDF statement parsers.

ICICI (and similar JasperReports) statements put transactions in the text
layer rather than extractable tables, so we parse line-by-line and infer
debit/credit from running balance changes.
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
    account_type_hint: str = "bank_account"  # saving / current → bank_account
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
        return Decimal(re.sub(r"[^\d.]", "", raw))
    except (InvalidOperation, TypeError):
        return None


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

        if re.search(r"Current\s+Account", text, re.I):
            meta.account_type_hint = "bank_account"

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
            # Rare rows with both withdrawal + deposit filled
            second = _to_decimal(amt_b) if amt_b else None
            balance = _to_decimal(bal_s)
            if amount is None or balance is None:
                continue

            # Remark lines sit after the numeric row until the next SNo line
            remark_parts: list[str] = []
            # Merchant/name often appears on the line *before* the numeric row
            if i > 0 and not TXN_LINE.match(lines[i - 1]):
                prev = lines[i - 1]
                if not re.search(r"S No\.|Withdrawal|Deposit|Balance|Statement of", prev, re.I):
                    if len(prev) < 80:
                        remark_parts.append(prev)

            for j in range(i + 1, min(i + 6, len(lines))):
                nxt = lines[j]
                if TXN_LINE.match(nxt):
                    break
                if re.match(r"^\d+$", nxt):  # page number
                    break
                remark_parts.append(nxt)

            description = " ".join(remark_parts).strip()
            description = re.sub(r"\s+", " ", description)

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

            # Explicit two-column row: withdrawal then deposit
            if second is not None and second > 0 and amount > 0:
                # Prefer the non-zero that matches the balance delta when possible
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
                # Heuristic from narration
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

            merchant = desc.split("/")[1] if desc.upper().startswith("UPI/") and "/" in desc[4:] else desc[:80]

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


PARSERS = [IciciStatementParser]


def detect_and_parse(text: str) -> ParsedStatement:
    for parser in PARSERS:
        if parser.matches(text):
            return parser.parse(text)
    raise ValueError(
        "Unrecognized bank statement format. Supported today: ICICI Bank PDF. "
        "Try exporting CSV from your bank, or pick an account manually for generic PDFs."
    )
