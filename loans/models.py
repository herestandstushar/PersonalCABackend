"""
Loans and EMI models.
"""
from django.conf import settings
from django.db import models

from core.models import BaseModel


class LoanStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    PAID_OFF = "paid_off", "Paid Off"
    DEFAULTED = "defaulted", "Defaulted"


class LoanType(models.TextChoices):
    HOME = "home", "Home Loan"
    CAR = "car", "Car Loan"
    PERSONAL = "personal", "Personal Loan"
    EDUCATION = "education", "Education Loan"
    OTHER = "other", "Other"


class Loan(BaseModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="loans",
    )
    name = models.CharField(max_length=255)
    loan_type = models.CharField(max_length=20, choices=LoanType.choices, default=LoanType.OTHER)
    
    principal_amount = models.DecimalField(max_digits=15, decimal_places=2)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2, help_text="Annual interest rate in %")
    tenure_months = models.IntegerField()
    
    emi_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    outstanding_balance = models.DecimalField(max_digits=15, decimal_places=2)
    
    start_date = models.DateField()
    status = models.CharField(max_length=20, choices=LoanStatus.choices, default=LoanStatus.ACTIVE)
    
    # The bank account the EMI gets deducted from
    linked_account = models.ForeignKey(
        "accounts.Account",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="loans",
    )

    class Meta:
        db_table = "loans"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.email} - {self.name} ({self.outstanding_balance})"

class EMIPayment(BaseModel):
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    principal_component = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    interest_component = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    payment_date = models.DateField()
    is_paid = models.BooleanField(default=False)
    
    transaction = models.ForeignKey(
        "transactions.Transaction", 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name="emi_payments"
    )

    class Meta:
        db_table = "emi_payments"
        ordering = ["-payment_date"]
