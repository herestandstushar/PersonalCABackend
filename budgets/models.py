"""
Budgets models.
"""

from django.conf import settings
from django.db import models

from core.models import BaseModel


class BudgetPeriod(models.TextChoices):
    WEEKLY = "weekly", "Weekly"
    MONTHLY = "monthly", "Monthly"
    YEARLY = "yearly", "Yearly"


class Budget(BaseModel):
    """
    User-defined budgets.
    Can be for a specific category or an overall budget (category=None).
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="budgets",
    )
    category = models.ForeignKey(
        "categories.Category",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="budgets",
        help_text="If null, this is an overall budget",
    )
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    period = models.CharField(
        max_length=20,
        choices=BudgetPeriod.choices,
        default=BudgetPeriod.MONTHLY,
    )
    is_rollover = models.BooleanField(
        default=False,
        help_text="Unspent amount rolls over to the next period",
    )
    is_active = models.BooleanField(default=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "budgets"
        unique_together = ["user", "category", "period"]

    def __str__(self):
        cat_name = self.category.name if self.category else "Overall"
        return f"{self.user.email} - {cat_name} ({self.period})"
