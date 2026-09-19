"""
Statements models.
"""
from django.conf import settings
from django.db import models

from core.models import BaseModel


class StatementStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    PROCESSING = "processing", "Processing"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"


class Statement(BaseModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="statements",
    )
    account = models.ForeignKey(
        "accounts.Account",
        on_delete=models.CASCADE,
        related_name="statements",
        null=True,
        blank=True,
        help_text="Filled automatically when a smart PDF import detects/creates the account.",
    )
    file = models.FileField(upload_to="statements/%Y/%m/")
    filename = models.CharField(max_length=255)
    status = models.CharField(
        max_length=20, 
        choices=StatementStatus.choices, 
        default=StatementStatus.PENDING
    )
    error_message = models.TextField(blank=True)
    transactions_imported = models.IntegerField(default=0)
    transactions_skipped = models.IntegerField(
        default=0,
        help_text="Rows skipped as duplicates of existing account transactions.",
    )
    month = models.IntegerField(null=True, blank=True)
    year = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = "statements"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.email} - {self.filename} ({self.status})"


class StatementMappingRule(BaseModel):
    """
    User-defined or system-defined mapping rules for a specific bank's statement format.
    E.g. Bank X uses 'Txn Date' for date, 'Narration' for description, etc.
    """
    name = models.CharField(max_length=100)
    date_column = models.CharField(max_length=50)
    description_column = models.CharField(max_length=50)
    amount_column = models.CharField(max_length=50, blank=True, help_text="If amounts are in a single column")
    debit_column = models.CharField(max_length=50, blank=True)
    credit_column = models.CharField(max_length=50, blank=True)
    date_format = models.CharField(max_length=50, default="%d/%m/%Y")
    
    is_global = models.BooleanField(default=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="statement_rules",
    )

    class Meta:
        db_table = "statement_mapping_rules"

    def __str__(self):
        return self.name
