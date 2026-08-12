"""
Transactions services — core business logic for financial transactions.
"""

import logging
from datetime import timedelta
from decimal import Decimal

from django.db import models, transaction as db_transaction
from django.db.models import Avg, Count, Q, Sum
from django.db.models.functions import TruncDate, TruncMonth, TruncWeek
from django.utils import timezone

from accounts.services import AccountService
from categories.services import CategoryService
from core.exceptions import DuplicateError, NotFoundError, ValidationError
from transactions.models import Transaction, TransactionType

logger = logging.getLogger("finsight")


class TransactionService:
    """Service layer for transaction operations."""

    @staticmethod
    @db_transaction.atomic
    def create_transaction(user, data: dict) -> Transaction:
        """
        Create a transaction and update account balances.

        - Auto-categorizes if no category provided
        - Checks for duplicates (same amount + date + merchant within 24h)
        - Updates source/destination account balances atomically
        """
        account = data.get("account")
        if account and account.user != user:
            raise ValidationError("Account does not belong to you.")

        # Inherit the account's currency when the client does not specify one
        if not data.get("currency"):
            if account is None:
                raise ValidationError("An account is required to create a transaction.")
            data["currency"] = account.currency

        # Auto-categorize if no category
        if not data.get("category"):
            merchant = data.get("merchant_name", "")
            description = data.get("description", "")
            auto_cat = CategoryService.auto_categorize(merchant, description)
            if auto_cat:
                data["category"] = auto_cat

        # Duplicate detection
        duplicate = TransactionService._check_duplicate(user, data)
        if duplicate:
            data["is_duplicate"] = True
            data["duplicate_of"] = duplicate

        txn = Transaction.objects.create(user=user, **data)

        # Update account balance
        if txn.is_credit:
            AccountService.update_balance(txn.account, txn.amount, is_credit=True)
        elif txn.is_debit:
            AccountService.update_balance(txn.account, txn.amount, is_credit=False)

        # Handle transfers — credit the destination
        if txn.transaction_type == TransactionType.TRANSFER and txn.to_account:
            AccountService.update_balance(txn.to_account, txn.amount, is_credit=True)

        logger.info(
            "Transaction created: %s %s %s for user %s",
            txn.transaction_type,
            txn.amount,
            txn.merchant_name,
            user.email,
        )
        return txn

    @staticmethod
    @db_transaction.atomic
    def update_transaction(user, txn_id, data: dict) -> Transaction:
        """Update a transaction, reversing and reapplying balance changes."""
        try:
            txn = Transaction.objects.select_related("account", "to_account").get(
                id=txn_id, user=user
            )
        except Transaction.DoesNotExist:
            raise NotFoundError("Transaction not found.")

        old_amount = txn.amount
        old_type = txn.transaction_type
        old_account = txn.account
        old_to_account = txn.to_account

        # Reverse old balance
        if txn.is_credit:
            AccountService.update_balance(old_account, old_amount, is_credit=False)
        elif txn.is_debit:
            AccountService.update_balance(old_account, old_amount, is_credit=True)
        if old_type == TransactionType.TRANSFER and old_to_account:
            AccountService.update_balance(old_to_account, old_amount, is_credit=False)

        # Apply updates
        for key, value in data.items():
            if hasattr(txn, key):
                setattr(txn, key, value)
        txn.save()
        txn.refresh_from_db()

        # Apply new balance
        if txn.is_credit:
            AccountService.update_balance(txn.account, txn.amount, is_credit=True)
        elif txn.is_debit:
            AccountService.update_balance(txn.account, txn.amount, is_credit=False)
        if txn.transaction_type == TransactionType.TRANSFER and txn.to_account:
            AccountService.update_balance(txn.to_account, txn.amount, is_credit=True)

        return txn

    @staticmethod
    @db_transaction.atomic
    def delete_transaction(user, txn_id):
        """Soft-delete a transaction and reverse the balance."""
        try:
            txn = Transaction.objects.select_related("account", "to_account").get(
                id=txn_id, user=user
            )
        except Transaction.DoesNotExist:
            raise NotFoundError("Transaction not found.")

        # Reverse balance
        if txn.is_credit:
            AccountService.update_balance(txn.account, txn.amount, is_credit=False)
        elif txn.is_debit:
            AccountService.update_balance(txn.account, txn.amount, is_credit=True)
        if txn.transaction_type == TransactionType.TRANSFER and txn.to_account:
            AccountService.update_balance(txn.to_account, txn.amount, is_credit=False)

        txn.soft_delete()
        logger.info("Transaction deleted: %s for user %s", txn_id, user.email)

    @staticmethod
    @db_transaction.atomic
    def bulk_create_transactions(user, transactions_data: list) -> list:
        """Bulk create transactions from statement import."""
        created = []
        for data in transactions_data:
            if data.get("skip"):
                continue
            txn = TransactionService.create_transaction(user, data)
            created.append(txn)
        return created

    @staticmethod
    def get_filtered_transactions(user, filters: dict = None):
        """
        Get transactions with advanced filtering.

        Supports: date_from, date_to, amount_min, amount_max, category,
        merchant, account, transaction_type, tags, search.
        """
        qs = Transaction.objects.filter(user=user).select_related(
            "category", "account", "currency", "to_account"
        )

        if not filters:
            return qs

        if filters.get("date_from"):
            qs = qs.filter(date__gte=filters["date_from"])
        if filters.get("date_to"):
            qs = qs.filter(date__lte=filters["date_to"])
        if filters.get("amount_min"):
            qs = qs.filter(amount__gte=filters["amount_min"])
        if filters.get("amount_max"):
            qs = qs.filter(amount__lte=filters["amount_max"])
        if filters.get("category"):
            qs = qs.filter(category_id=filters["category"])
        if filters.get("categories"):
            qs = qs.filter(category_id__in=filters["categories"])
        if filters.get("merchant"):
            qs = qs.filter(merchant_name__icontains=filters["merchant"])
        if filters.get("account"):
            qs = qs.filter(account_id=filters["account"])
        if filters.get("transaction_type"):
            qs = qs.filter(transaction_type=filters["transaction_type"])
        if filters.get("transaction_types"):
            qs = qs.filter(transaction_type__in=filters["transaction_types"])
        if filters.get("payment_method"):
            qs = qs.filter(payment_method=filters["payment_method"])
        if filters.get("tags"):
            qs = qs.filter(tags__overlap=filters["tags"])
        if filters.get("search"):
            search_term = filters["search"]
            qs = qs.filter(
                Q(merchant_name__icontains=search_term)
                | Q(description__icontains=search_term)
                | Q(notes__icontains=search_term)
            )
        if filters.get("is_recurring") is not None:
            qs = qs.filter(is_recurring=filters["is_recurring"])

        return qs

    @staticmethod
    def get_spending_summary(user, period="month"):
        """Get spending aggregated by period (today, week, month, year)."""
        now = timezone.now()
        today = now.date()

        base_qs = Transaction.objects.filter(
            user=user,
            transaction_type__in=[
                TransactionType.EXPENSE,
                TransactionType.RECURRING_EXPENSE,
            ],
        )

        today_spent = base_qs.filter(date=today).aggregate(
            total=Sum("amount")
        )["total"] or Decimal("0")

        week_start = today - timedelta(days=today.weekday())
        week_spent = base_qs.filter(date__gte=week_start).aggregate(
            total=Sum("amount")
        )["total"] or Decimal("0")

        month_spent = base_qs.filter(
            date__year=today.year, date__month=today.month
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

        year_spent = base_qs.filter(date__year=today.year).aggregate(
            total=Sum("amount")
        )["total"] or Decimal("0")

        return {
            "today": today_spent,
            "this_week": week_spent,
            "this_month": month_spent,
            "this_year": year_spent,
        }

    @staticmethod
    def get_income_summary(user):
        """Get income for current month."""
        now = timezone.now()
        today = now.date()

        income_qs = Transaction.objects.filter(
            user=user,
            transaction_type__in=[
                TransactionType.INCOME,
                TransactionType.RECURRING_INCOME,
            ],
        )

        month_income = income_qs.filter(
            date__year=today.year, date__month=today.month
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

        return {"this_month": month_income}

    @staticmethod
    def get_category_breakdown(user, date_from=None, date_to=None):
        """Get spending breakdown by category for a date range."""
        now = timezone.now()
        if not date_from:
            date_from = now.date().replace(day=1)
        if not date_to:
            date_to = now.date()

        breakdown = (
            Transaction.objects.filter(
                user=user,
                date__gte=date_from,
                date__lte=date_to,
                transaction_type__in=[
                    TransactionType.EXPENSE,
                    TransactionType.RECURRING_EXPENSE,
                ],
            )
            .values("category__name", "category__icon", "category__color")
            .annotate(total=Sum("amount"), count=Count("id"))
            .order_by("-total")
        )

        return list(breakdown)

    @staticmethod
    def get_merchant_breakdown(user, date_from=None, date_to=None, limit=10):
        """Get spending breakdown by merchant."""
        now = timezone.now()
        if not date_from:
            date_from = now.date().replace(day=1)
        if not date_to:
            date_to = now.date()

        breakdown = (
            Transaction.objects.filter(
                user=user,
                date__gte=date_from,
                date__lte=date_to,
                transaction_type__in=[
                    TransactionType.EXPENSE,
                    TransactionType.RECURRING_EXPENSE,
                ],
                merchant_name__gt="",
            )
            .values("merchant_name")
            .annotate(total=Sum("amount"), count=Count("id"))
            .order_by("-total")[:limit]
        )

        return list(breakdown)

    @staticmethod
    def get_payment_method_breakdown(user, date_from=None, date_to=None):
        """Get spending breakdown by payment method."""
        now = timezone.now()
        if not date_from:
            date_from = now.date().replace(day=1)
        if not date_to:
            date_to = now.date()

        breakdown = (
            Transaction.objects.filter(
                user=user,
                date__gte=date_from,
                date__lte=date_to,
                transaction_type__in=[
                    TransactionType.EXPENSE,
                    TransactionType.RECURRING_EXPENSE,
                ],
            )
            .values("payment_method")
            .annotate(total=Sum("amount"), count=Count("id"))
            .order_by("-total")
        )

        return list(breakdown)

    @staticmethod
    def get_cash_flow(user, months=6):
        """Get monthly income vs expense for cash flow chart."""
        now = timezone.now()
        from_date = (now - timedelta(days=30 * months)).date().replace(day=1)

        income_types = [TransactionType.INCOME, TransactionType.RECURRING_INCOME, TransactionType.REFUND]
        expense_types = [TransactionType.EXPENSE, TransactionType.RECURRING_EXPENSE, TransactionType.EMI, TransactionType.LOAN_PAYMENT]

        monthly_data = (
            Transaction.objects.filter(user=user, date__gte=from_date)
            .annotate(month=TruncMonth("date"))
            .values("month")
            .annotate(
                income=Sum("amount", filter=Q(transaction_type__in=income_types)),
                expense=Sum("amount", filter=Q(transaction_type__in=expense_types)),
            )
            .order_by("month")
        )

        result = []
        for entry in monthly_data:
            income = entry["income"] or Decimal("0")
            expense = entry["expense"] or Decimal("0")
            result.append({
                "month": entry["month"].strftime("%Y-%m"),
                "income": float(income),
                "expense": float(expense),
                "savings": float(income - expense),
            })

        return result

    @staticmethod
    def get_daily_spending(user, days=30):
        """Get daily spending for the last N days."""
        from_date = timezone.now().date() - timedelta(days=days)

        daily = (
            Transaction.objects.filter(
                user=user,
                date__gte=from_date,
                transaction_type__in=[
                    TransactionType.EXPENSE,
                    TransactionType.RECURRING_EXPENSE,
                ],
            )
            .annotate(day=TruncDate("date"))
            .values("day")
            .annotate(total=Sum("amount"))
            .order_by("day")
        )

        return [{"date": d["day"].isoformat(), "amount": float(d["total"])} for d in daily]

    @staticmethod
    def get_top_transactions(user, limit=10, date_from=None, date_to=None):
        """Get top N largest transactions."""
        now = timezone.now()
        if not date_from:
            date_from = now.date().replace(day=1)
        if not date_to:
            date_to = now.date()

        return (
            Transaction.objects.filter(
                user=user,
                date__gte=date_from,
                date__lte=date_to,
                transaction_type__in=[
                    TransactionType.EXPENSE,
                    TransactionType.RECURRING_EXPENSE,
                ],
            )
            .select_related("category", "account")
            .order_by("-amount")[:limit]
        )

    @staticmethod
    def _check_duplicate(user, data: dict):
        """
        Check for potential duplicates.
        Same amount + date + merchant within existing transactions.
        """
        amount = data.get("amount")
        date = data.get("date")
        merchant = data.get("merchant_name", "")

        if not amount or not date:
            return None

        qs = Transaction.objects.filter(
            user=user,
            amount=amount,
            date=date,
        )

        if merchant:
            qs = qs.filter(merchant_name__iexact=merchant)

        existing = qs.first()
        return existing
