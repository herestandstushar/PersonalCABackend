"""
Savings services.
"""

from decimal import Decimal, InvalidOperation

from django.db import transaction as db_transaction
from savings.models import SavingsGoal, GoalContribution, SavingsGoalStatus
from core.exceptions import ValidationError

class SavingsService:
    @staticmethod
    @db_transaction.atomic
    def add_contribution(user, goal_id, amount, notes=""):
        try:
            amount = Decimal(str(amount))
        except (TypeError, InvalidOperation):
            raise ValidationError("Contribution amount must be a number.")

        if amount <= 0:
            raise ValidationError("Contribution amount must be positive.")


        try:
            goal = SavingsGoal.objects.get(id=goal_id, user=user)
        except SavingsGoal.DoesNotExist:
            raise ValidationError("Savings goal not found.")
            
        if goal.status != SavingsGoalStatus.ACTIVE:
            raise ValidationError("Cannot contribute to a non-active goal.")
            
        contribution = GoalContribution.objects.create(
            goal=goal,
            amount=amount,
            notes=notes
        )
        
        goal.current_amount += amount
        if goal.current_amount >= goal.target_amount:
            goal.status = SavingsGoalStatus.COMPLETED
            
        goal.save()
        return contribution
