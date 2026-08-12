"""
Subscriptions models.
"""
from django.conf import settings
from django.db import models

from core.models import BaseModel


class BillingCycle(models.TextChoices):
    MONTHLY = "monthly", "Monthly"
    YEARLY = "yearly", "Yearly"
    QUARTERLY = "quarterly", "Quarterly"
    WEEKLY = "weekly", "Weekly"


class SubscriptionStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    CANCELLED = "cancelled", "Cancelled"
    PAUSED = "paused", "Paused"


class Subscription(BaseModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="subscriptions",
    )
    name = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    billing_cycle = models.CharField(
        max_length=20, 
        choices=BillingCycle.choices, 
        default=BillingCycle.MONTHLY
    )
    next_billing_date = models.DateField()
    
    category = models.ForeignKey(
        "categories.Category",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subscriptions",
    )
    account = models.ForeignKey(
        "accounts.Account",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Account used to pay for this subscription",
    )
    
    status = models.CharField(
        max_length=20,
        choices=SubscriptionStatus.choices,
        default=SubscriptionStatus.ACTIVE
    )
    auto_renew = models.BooleanField(default=True)
    url = models.URLField(blank=True)
    color = models.CharField(max_length=20, default="#d946ef")
    icon = models.CharField(max_length=50, default="repeat")

    class Meta:
        db_table = "subscriptions"
        ordering = ["next_billing_date"]

    def __str__(self):
        return f"{self.user.email} - {self.name} ({self.amount})"


class RecurringTransaction(BaseModel):
    """
    A template for generating transactions on a regular schedule (e.g. rent, salary).
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="recurring_transactions",
    )
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    transaction_type = models.CharField(max_length=20)  # e.g. income, expense
    
    frequency = models.CharField(
        max_length=20,
        choices=BillingCycle.choices,
        default=BillingCycle.MONTHLY
    )
    category = models.ForeignKey("categories.Category", on_delete=models.SET_NULL, null=True, blank=True)
    account = models.ForeignKey("accounts.Account", on_delete=models.CASCADE)
    
    next_date = models.DateField()
    is_active = models.BooleanField(default=True)
    last_processed_date = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "recurring_transactions"

    def __str__(self):
        return f"{self.description} - {self.frequency}"
