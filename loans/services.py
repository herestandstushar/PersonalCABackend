"""
Loans services.
"""
from decimal import Decimal
import math

class LoanService:
    @staticmethod
    def calculate_emi(principal, annual_rate, tenure_months):
        """
        Calculates the Equated Monthly Installment (EMI).
        Formula: E = P * r * (1 + r)^n / ((1 + r)^n - 1)
        Where:
        P = Principal
        r = Monthly interest rate (annual_rate / 12 / 100)
        n = Tenure in months
        """
        if annual_rate == 0:
            return Decimal(str(round(float(principal) / float(tenure_months), 2)))


        r = (float(annual_rate) / 12) / 100
        P = float(principal)
        n = int(tenure_months)
        
        emi = P * r * (math.pow(1 + r, n)) / (math.pow(1 + r, n) - 1)
        return Decimal(str(round(emi, 2)))

    @staticmethod
    def setup_loan(loan):
        """Initializes a new loan with calculated EMI."""
        if not loan.emi_amount:
            loan.emi_amount = LoanService.calculate_emi(
                loan.principal_amount, 
                loan.interest_rate, 
                loan.tenure_months
            )
        
        if loan.outstanding_balance is None:
            loan.outstanding_balance = loan.principal_amount
            
        loan.save()
        return loan
