"""
Subscriptions services.
"""
from datetime import timedelta
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from django.db import transaction as db_transaction

from subscriptions.models import Subscription, SubscriptionStatus, RecurringTransaction, BillingCycle
from transactions.models import TransactionSource
from transactions.services import TransactionService

class SubscriptionService:
    @staticmethod
    def _calculate_next_date(current_date, frequency):
        if frequency == BillingCycle.MONTHLY:
            return current_date + relativedelta(months=1)
        elif frequency == BillingCycle.YEARLY:
            return current_date + relativedelta(years=1)
        elif frequency == BillingCycle.QUARTERLY:
            return current_date + relativedelta(months=3)
        elif frequency == BillingCycle.WEEKLY:
            return current_date + timedelta(days=7)
        return current_date + timedelta(days=30)

    @staticmethod
    def process_due_subscriptions():
        """
        Background task to process subscriptions that are due today.
        In a real app, this would be a Celery beat task running daily.
        """
        today = timezone.now().date()
        
        # Process Subscriptions
        due_subs = Subscription.objects.filter(
            status=SubscriptionStatus.ACTIVE,
            next_billing_date__lte=today,
            auto_renew=True,
            account__isnull=False
        )
        
        for sub in due_subs:
            with db_transaction.atomic():
                # Create transaction
                txn_data = {
                    "account": sub.account,
                    "transaction_type": "recurring_expense",
                    "amount": sub.amount,
                    "date": sub.next_billing_date,
                    "description": sub.name,
                    "merchant_name": sub.name,
                    "category": sub.category,
                    "source": TransactionSource.SYSTEM
                }
                TransactionService.create_transaction(sub.user, txn_data)
                
                # Update next billing date
                sub.next_billing_date = SubscriptionService._calculate_next_date(sub.next_billing_date, sub.billing_cycle)
                sub.save()

    @staticmethod
    def process_due_recurring_transactions():
        """Process recurring general transactions (salary, rent)."""
        today = timezone.now().date()
        
        due_recurring = RecurringTransaction.objects.filter(
            is_active=True,
            next_date__lte=today
        )
        
        for rec in due_recurring:
            with db_transaction.atomic():
                txn_data = {
                    "account": rec.account,
                    "transaction_type": rec.transaction_type,
                    "amount": rec.amount,
                    "date": rec.next_date,
                    "description": rec.description,
                    "category": rec.category,
                    "source": TransactionSource.SYSTEM
                }
                TransactionService.create_transaction(rec.user, txn_data)
                
                rec.last_processed_date = rec.next_date
                rec.next_date = SubscriptionService._calculate_next_date(rec.next_date, rec.frequency)
                rec.save()
