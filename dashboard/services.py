"""
Dashboard services — aggregation service for the main dashboard.

Single endpoint that returns all data needed for the home dashboard,
cached in Redis for 5 minutes to avoid expensive re-computation.
"""

import logging
from decimal import Decimal

from django.core.cache import cache
from django.utils import timezone

from accounts.services import AccountService
from transactions.models import Transaction, TransactionType
from transactions.services import TransactionService

logger = logging.getLogger("finsight")

DASHBOARD_CACHE_TTL = 300  # 5 minutes


class DashboardService:
    """Aggregation service for dashboard data."""

    @staticmethod
    def get_full_dashboard(user) -> dict:
        """
        Get complete dashboard data — cached for performance.

        Returns all widgets data in a single response to minimize
        frontend API calls and ensure atomic data consistency.
        """
        cache_key = f"dashboard:{user.id}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        data = DashboardService._compute_dashboard(user)
        cache.set(cache_key, data, DASHBOARD_CACHE_TTL)
        return data

    @staticmethod
    def invalidate_cache(user):
        """Invalidate dashboard cache when data changes."""
        cache.delete(f"dashboard:{user.id}")

    @staticmethod
    def get_widget_data(user, widget_name: str) -> dict:
        """Get data for a single dashboard widget (for lazy loading)."""
        widget_map = {
            "overview": DashboardService._get_overview,
            "spending": DashboardService._get_spending,
            "income": DashboardService._get_income,
            "cash_flow": DashboardService._get_cash_flow,
            "categories": DashboardService._get_category_breakdown,
            "merchants": DashboardService._get_merchant_breakdown,
            "recent_transactions": DashboardService._get_recent_transactions,
            "payment_methods": DashboardService._get_payment_methods,
            "daily_spending": DashboardService._get_daily_spending,
            "top_expenses": DashboardService._get_top_expenses,
            "financial_health": DashboardService._get_financial_health,
        }

        handler = widget_map.get(widget_name)
        if not handler:
            return {"error": f"Unknown widget: {widget_name}"}

        return handler(user)

    @staticmethod
    def _compute_dashboard(user) -> dict:
        """Compute all dashboard data. Called when cache misses."""
        return {
            "overview": DashboardService._get_overview(user),
            "spending": DashboardService._get_spending(user),
            "income": DashboardService._get_income(user),
            "cash_flow": DashboardService._get_cash_flow(user),
            "categories": DashboardService._get_category_breakdown(user),
            "merchants": DashboardService._get_merchant_breakdown(user),
            "recent_transactions": DashboardService._get_recent_transactions(user),
            "payment_methods": DashboardService._get_payment_methods(user),
            "daily_spending": DashboardService._get_daily_spending(user),
            "top_expenses": DashboardService._get_top_expenses(user),
            "financial_health": DashboardService._get_financial_health(user),
        }

    @staticmethod
    def _get_overview(user) -> dict:
        """Net worth, total balance, savings rate."""
        balances = AccountService.get_total_balance(user)
        income = TransactionService.get_income_summary(user)
        spending = TransactionService.get_spending_summary(user)

        month_income = income["this_month"]
        month_expense = spending["this_month"]
        savings = month_income - month_expense
        savings_rate = (
            float((savings / month_income) * 100) if month_income > 0 else 0
        )

        return {
            "net_worth": float(balances["net_worth"]),
            "total_assets": float(balances["total_assets"]),
            "total_liabilities": float(balances["total_liabilities"]),
            "savings_this_month": float(savings),
            "savings_rate": round(savings_rate, 1),
        }

    @staticmethod
    def _get_spending(user) -> dict:
        return {
            k: float(v)
            for k, v in TransactionService.get_spending_summary(user).items()
        }

    @staticmethod
    def _get_income(user) -> dict:
        return {
            k: float(v)
            for k, v in TransactionService.get_income_summary(user).items()
        }

    @staticmethod
    def _get_cash_flow(user) -> list:
        return TransactionService.get_cash_flow(user, months=6)

    @staticmethod
    def _get_category_breakdown(user) -> list:
        raw = TransactionService.get_category_breakdown(user)
        return [
            {
                "name": item["category__name"] or "Uncategorized",
                "icon": item["category__icon"] or "tag",
                "color": item["category__color"] or "#94a3b8",
                "total": float(item["total"]),
                "count": item["count"],
            }
            for item in raw
        ]

    @staticmethod
    def _get_merchant_breakdown(user) -> list:
        raw = TransactionService.get_merchant_breakdown(user, limit=10)
        return [
            {
                "name": item["merchant_name"],
                "total": float(item["total"]),
                "count": item["count"],
            }
            for item in raw
        ]

    @staticmethod
    def _get_recent_transactions(user) -> list:
        from transactions.serializers import TransactionSerializer

        txns = Transaction.objects.filter(user=user).select_related(
            "category", "account", "currency"
        ).order_by("-date", "-created_at")[:10]

        return TransactionSerializer(txns, many=True).data

    @staticmethod
    def _get_payment_methods(user) -> list:
        raw = TransactionService.get_payment_method_breakdown(user)
        return [
            {
                "method": item["payment_method"],
                "total": float(item["total"]),
                "count": item["count"],
            }
            for item in raw
        ]

    @staticmethod
    def _get_daily_spending(user) -> list:
        return TransactionService.get_daily_spending(user, days=30)

    @staticmethod
    def _get_top_expenses(user) -> list:
        from transactions.serializers import TransactionSerializer

        txns = TransactionService.get_top_transactions(user, limit=5)
        return TransactionSerializer(txns, many=True).data

    @staticmethod
    def _get_financial_health(user) -> dict:
        """
        Compute a financial health score (0-100) based on:
        - Savings rate (0-40 points)
        - Debt ratio (0-30 points)
        - Budget adherence (0-30 points) — placeholder for now
        """
        overview = DashboardService._get_overview(user)
        savings_rate = overview.get("savings_rate", 0)

        # Savings rate score (0-40): 20%+ savings = full marks
        savings_score = min(savings_rate * 2, 40)

        # Debt ratio score (0-30): lower liabilities relative to assets = better
        assets = overview.get("total_assets", 0)
        liabilities = overview.get("total_liabilities", 0)
        if assets > 0:
            debt_ratio = liabilities / assets
            debt_score = max(0, 30 * (1 - debt_ratio))
        else:
            debt_score = 15  # Neutral if no assets

        # Budget adherence (placeholder: 20 points for now)
        budget_score = 20

        total_score = round(savings_score + debt_score + budget_score)
        total_score = max(0, min(100, total_score))

        # Determine label
        if total_score >= 80:
            label = "Excellent"
            color = "#22c55e"
        elif total_score >= 60:
            label = "Good"
            color = "#84cc16"
        elif total_score >= 40:
            label = "Fair"
            color = "#eab308"
        elif total_score >= 20:
            label = "Needs Work"
            color = "#f97316"
        else:
            label = "Critical"
            color = "#ef4444"

        return {
            "score": total_score,
            "label": label,
            "color": color,
            "breakdown": {
                "savings": round(savings_score),
                "debt": round(debt_score),
                "budget": round(budget_score),
            },
        }
