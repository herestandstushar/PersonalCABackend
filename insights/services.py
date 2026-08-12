"""
AI Insights Service.
"""
from datetime import timedelta
from django.utils import timezone
from django.db.models import Sum

from transactions.models import Transaction, TransactionType
from categories.models import Category

class InsightsService:
    @staticmethod
    def generate_insights(user):
        """
        Rule-based insights generation.
        In the future, this can serialize this data and pass it to an LLM.
        """
        insights = []
        today = timezone.now().date()
        thirty_days_ago = today - timedelta(days=30)
        sixty_days_ago = today - timedelta(days=60)
        
        # 1. Compare last 30 days vs previous 30 days spending
        current_month_spend = Transaction.objects.filter(
            user=user, 
            date__gte=thirty_days_ago, 
            date__lte=today,
            transaction_type=TransactionType.EXPENSE
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        prev_month_spend = Transaction.objects.filter(
            user=user, 
            date__gte=sixty_days_ago, 
            date__lt=thirty_days_ago,
            transaction_type=TransactionType.EXPENSE
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        if prev_month_spend > 0:
            diff_pct = ((current_month_spend - prev_month_spend) / prev_month_spend) * 100
            if diff_pct > 15:
                insights.append({
                    "type": "warning",
                    "title": "Spending Alert",
                    "message": f"Your spending is up {diff_pct:.0f}% compared to the previous 30 days.",
                    "icon": "trending-up",
                    "action_text": "Review Budgets",
                    "action_url": "/budgets"
                })
            elif diff_pct < -10:
                insights.append({
                    "type": "success",
                    "title": "Great Savings!",
                    "message": f"You've spent {abs(diff_pct):.0f}% less in the last 30 days. Keep it up!",
                    "icon": "trending-down",
                    "action_text": "Add to Savings",
                    "action_url": "/savings"
                })

        # 2. Large Transactions Anomaly
        # Find transactions > 3x average transaction size in last 30 days
        recent_txns = Transaction.objects.filter(
            user=user, date__gte=thirty_days_ago, transaction_type=TransactionType.EXPENSE
        )
        if recent_txns.exists():
            avg_txn = sum(t.amount for t in recent_txns) / recent_txns.count()
            large_txns = [t for t in recent_txns if t.amount > avg_txn * 3]
            if large_txns:
                insights.append({
                    "type": "info",
                    "title": "Unusual Spending Detected",
                    "message": f"You had {len(large_txns)} unusually large transactions recently, including {large_txns[0].merchant_name} ({large_txns[0].amount}).",
                    "icon": "alert-circle",
                    "action_text": "Review Transactions",
                    "action_url": "/transactions"
                })

        # If no insights, return a default positive one
        if not insights:
            insights.append({
                "type": "neutral",
                "title": "On Track",
                "message": "Your financial habits are looking steady. No anomalies detected.",
                "icon": "check-circle",
                "action_text": "View Dashboard",
                "action_url": "/"
            })

        return insights
