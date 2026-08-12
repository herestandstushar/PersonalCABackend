"""
Savings models.
"""
from django.conf import settings
from django.db import models

from core.models import BaseModel


class SavingsGoalStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"


class SavingsGoal(BaseModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="savings_goals",
    )
    name = models.CharField(max_length=255)
    target_amount = models.DecimalField(max_digits=15, decimal_places=2)
    current_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    target_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20, 
        choices=SavingsGoalStatus.choices, 
        default=SavingsGoalStatus.ACTIVE
    )
    icon = models.CharField(max_length=50, default="target")
    color = models.CharField(max_length=20, default="#3b82f6")
    notes = models.TextField(blank=True)
    
    # Optional link to a specific account where these savings live
    linked_account = models.ForeignKey(
        "accounts.Account",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="savings_goals",
    )

    class Meta:
        db_table = "savings_goals"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.email} - {self.name} ({self.current_amount}/{self.target_amount})"

    @property
    def progress_percentage(self):
        if self.target_amount > 0:
            return min(100, float((self.current_amount / self.target_amount) * 100))
        return 0


class GoalContribution(BaseModel):
    """Tracks manual or automatic additions to a savings goal."""
    goal = models.ForeignKey(
        SavingsGoal,
        on_delete=models.CASCADE,
        related_name="contributions"
    )
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    date = models.DateField(auto_now_add=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "goal_contributions"
        ordering = ["-date", "-created_at"]
