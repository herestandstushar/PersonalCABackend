"""
Accounts models — Bank Accounts, Credit Cards, Wallets, Cash, UPI.
"""

from django.conf import settings
from django.db import models

from core.models import BaseModel


class AccountType(models.TextChoices):
    BANK_ACCOUNT = "bank_account", "Bank Account"
    CREDIT_CARD = "credit_card", "Credit Card"
    WALLET = "wallet", "Wallet"
    CASH = "cash", "Cash"
    UPI = "upi", "UPI"


class Account(BaseModel):
    """
    Financial account — represents a bank account, credit card, wallet,
    cash pocket, or UPI account.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="accounts",
    )
    name = models.CharField(max_length=200, help_text="Display name, e.g. 'HDFC Savings'")
    account_type = models.CharField(
        max_length=20,
        choices=AccountType.choices,
        db_index=True,
    )
    bank_name = models.CharField(max_length=200, blank=True)
    account_number_encrypted = models.TextField(
        blank=True,
        help_text="Encrypted account/card number",
    )
    statement_password_encrypted = models.TextField(
        blank=True,
        help_text="Encrypted PDF statement password for this account (never returned in API).",
    )
    currency = models.ForeignKey(
        "users.Currency",
        on_delete=models.PROTECT,
        related_name="accounts",
    )
    current_balance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
    )
    credit_limit = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Credit limit (for credit cards only)",
    )
    color = models.CharField(
        max_length=7,
        default="#6366f1",
        help_text="Hex color for UI display",
    )
    icon = models.CharField(
        max_length=50,
        default="wallet",
        help_text="Lucide icon name",
    )
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(
        default=False,
        help_text="Default account for new transactions",
    )
    last_synced = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "accounts"
        ordering = ["-is_default", "-is_active", "name"]
        indexes = [
            models.Index(fields=["user", "account_type"]),
            models.Index(fields=["user", "is_active"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_account_type_display()})"

    @property
    def available_credit(self):
        """For credit cards: credit_limit - current_balance (balance is debt)."""
        if self.account_type == AccountType.CREDIT_CARD and self.credit_limit:
            return self.credit_limit - self.current_balance
        return None

    @property
    def credit_utilization(self):
        """For credit cards: percentage of credit limit used."""
        if (
            self.account_type == AccountType.CREDIT_CARD
            and self.credit_limit
            and self.credit_limit > 0
        ):
            return round((self.current_balance / self.credit_limit) * 100, 1)
        return None
