"""
Budgets services.
"""

from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum, Q

from budgets.models import Budget, BudgetPeriod
from core.exceptions import ValidationError, NotFoundError
from transactions.models import Transaction, TransactionType


class BudgetService:
    @staticmethod
    def get_budget_status(user, period_date=None):
        """
        Calculate how much has been spent against each active budget.
        """
        if not period_date:
            period_date = timezone.now().date()

        budgets = Budget.objects.filter(user=user, is_active=True).select_related("category")
        results = []

        # Optimization: get all expenses for the current month/week/year based on budgets needed
        # For simplicity, calculate per budget
        for budget in budgets:
            # Determine date range based on period
            if budget.period == BudgetPeriod.MONTHLY:
                start_date = period_date.replace(day=1)
                # handle end of month
                if period_date.month == 12:
                    end_date = period_date.replace(year=period_date.year + 1, month=1, day=1)
                else:
                    end_date = period_date.replace(month=period_date.month + 1, day=1)
            elif budget.period == BudgetPeriod.YEARLY:
                start_date = period_date.replace(month=1, day=1)
                end_date = period_date.replace(year=period_date.year + 1, month=1, day=1)
            else: # Weekly
                start_date = period_date - timezone.timedelta(days=period_date.weekday())
                end_date = start_date + timezone.timedelta(days=7)

            # Filter transactions
            qs = Transaction.objects.filter(
                user=user,
                date__gte=start_date,
                date__lt=end_date,
                transaction_type__in=[TransactionType.EXPENSE, TransactionType.RECURRING_EXPENSE],
            )

            if budget.category:
                # include subcategories
                qs = qs.filter(Q(category=budget.category) | Q(category__parent=budget.category))

            spent = qs.aggregate(total=Sum("amount"))["total"] or Decimal("0")
            
            # Simple rollover logic: in a full app, we'd look back at previous months' unused budgets
            # For MVP, we just calculate current month spent vs total amount
            available = budget.amount - spent
            percentage = float((spent / budget.amount) * 100) if budget.amount > 0 else 0

            results.append({
                "budget_id": budget.id,
                "category_id": budget.category_id,
                "category_name": budget.category.name if budget.category else "Overall",
                "category_color": budget.category.color if budget.category else "#6366f1",
                "category_icon": budget.category.icon if budget.category else "target",
                "amount": float(budget.amount),
                "spent": float(spent),
                "available": float(available),
                "percentage_used": min(percentage, 100),
                "is_over_budget": spent > budget.amount,
                "period": budget.period,
            })

        return results

    @staticmethod
    def create_budget(user, data):
        # Enforce unique constraint
        existing = Budget.objects.filter(
            user=user, 
            category_id=data.get("category"), 
            period=data.get("period", BudgetPeriod.MONTHLY)
        ).exists()
        
        if existing:
            raise ValidationError("A budget for this category and period already exists.")
            
        return Budget.objects.create(user=user, **data)
