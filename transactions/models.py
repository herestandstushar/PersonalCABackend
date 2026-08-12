"""
Transactions models — the core financial data model.

Supports: expense, income, transfer, refund, investment, loan_payment,
emi, recurring_expense, recurring_income.
"""

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models

from core.models import BaseModel


class TransactionType(models.TextChoices):
    EXPENSE = "expense", "Expense"
    INCOME = "income", "Income"
    TRANSFER = "transfer", "Transfer"
    REFUND = "refund", "Refund"
    INVESTMENT = "investment", "Investment"
    LOAN_PAYMENT = "loan_payment", "Loan Payment"
    EMI = "emi", "EMI"
    RECURRING_EXPENSE = "recurring_expense", "Recurring Expense"
    RECURRING_INCOME = "recurring_income", "Recurring Income"


class PaymentMethod(models.TextChoices):
    CASH = "cash", "Cash"
    UPI = "upi", "UPI"
    DEBIT_CARD = "debit_card", "Debit Card"
    CREDIT_CARD = "credit_card", "Credit Card"
    NET_BANKING = "net_banking", "Net Banking"
    WALLET = "wallet", "Wallet"
    AUTO_DEBIT = "auto_debit", "Auto Debit"
    CHEQUE = "cheque", "Cheque"
    OTHER = "other", "Other"


class TransactionSource(models.TextChoices):
    MANUAL = "manual", "Manual"
    STATEMENT_IMPORT = "statement_import", "Statement Import"
    RECURRING = "recurring", "Recurring"
    API = "api", "API"


class Transaction(BaseModel):
    """
    Core transaction model — every financial movement.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="transactions",
    )
    transaction_type = models.CharField(
        max_length=20,
        choices=TransactionType.choices,
        db_index=True,
    )
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    currency = models.ForeignKey(
        "users.Currency",
        on_delete=models.PROTECT,
        related_name="transactions",
    )
    exchange_rate = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        default=1.0,
        help_text="Exchange rate to user's default currency at transaction time",
    )
    date = models.DateField(db_index=True)
    time = models.TimeField(null=True, blank=True)
    merchant_name = models.CharField(max_length=300, blank=True, db_index=True)
    description = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    # Relationships
    category = models.ForeignKey(
        "categories.Category",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transactions",
    )
    account = models.ForeignKey(
        "accounts.Account",
        on_delete=models.CASCADE,
        related_name="transactions",
    )
    to_account = models.ForeignKey(
        "accounts.Account",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="incoming_transfers",
        help_text="Destination account for transfers",
    )

    # Payment info
    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        default=PaymentMethod.OTHER,
    )

    # Metadata
    tags = ArrayField(
        models.CharField(max_length=50),
        default=list,
        blank=True,
    )
    receipt_image = models.ImageField(
        upload_to="receipts/",
        null=True,
        blank=True,
    )
    source = models.CharField(
        max_length=20,
        choices=TransactionSource.choices,
        default=TransactionSource.MANUAL,
    )
    is_recurring = models.BooleanField(default=False)
    is_duplicate = models.BooleanField(default=False)
    duplicate_of = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="duplicates",
    )
    statement_reference = models.CharField(
        max_length=500,
        blank=True,
        help_text="Reference from bank statement for dedup",
    )

    class Meta:
        db_table = "transactions"
        ordering = ["-date", "-created_at"]
        indexes = [
            models.Index(fields=["user", "date"]),
            models.Index(fields=["user", "category"]),
            models.Index(fields=["user", "transaction_type"]),
            models.Index(fields=["user", "merchant_name"]),
            models.Index(fields=["user", "account"]),
            models.Index(fields=["user", "-date", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.transaction_type}: {self.amount} — {self.merchant_name or self.description}"

    @property
    def is_credit(self):
        """Whether this transaction adds money to the account."""
        return self.transaction_type in (
            TransactionType.INCOME,
            TransactionType.REFUND,
            TransactionType.RECURRING_INCOME,
        )

    @property
    def is_debit(self):
        """Whether this transaction removes money from the account."""
        return self.transaction_type in (
            TransactionType.EXPENSE,
            TransactionType.INVESTMENT,
            TransactionType.LOAN_PAYMENT,
            TransactionType.EMI,
            TransactionType.RECURRING_EXPENSE,
        )

    @property
    def amount_in_default_currency(self):
        """Amount converted to user's default currency."""
        return self.amount * self.exchange_rate
