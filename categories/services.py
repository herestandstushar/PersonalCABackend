"""
Categories services — business logic for categorization.
"""

import logging

from categories.models import Category, CategoryType, SYSTEM_CATEGORIES

logger = logging.getLogger("finsight")


class CategoryService:
    """Service layer for category operations."""

    @staticmethod
    def get_user_categories(user, category_type=None):
        """
        Get all categories available to a user (system + custom).
        """
        qs = Category.objects.filter(
            models.Q(is_system=True) | models.Q(user=user)
        ).select_related("parent")

        if category_type:
            qs = qs.filter(category_type=category_type)

        return qs

    @staticmethod
    def create_custom_category(user, data: dict) -> Category:
        """Create a user-custom category."""
        return Category.objects.create(user=user, is_system=False, **data)

    @staticmethod
    def auto_categorize(
        merchant_name: str,
        description: str = "",
        transaction_type: str | None = None,
    ) -> Category | None:
        """
        Auto-categorize a transaction based on merchant name and description.

        Uses keyword matching against system categories. When transaction_type
        is provided, prefer categories of that type (income vs expense).
        """
        if not merchant_name and not description:
            return None

        search_text = f"{merchant_name} {description}".lower()

        system_categories = Category.objects.filter(is_system=True).exclude(
            keywords=[]
        )
        if transaction_type == "income":
            system_categories = system_categories.filter(
                category_type=CategoryType.INCOME
            )
        elif transaction_type == "expense":
            system_categories = system_categories.filter(
                category_type=CategoryType.EXPENSE
            )

        best_match = None
        best_score = 0

        for category in system_categories:
            score = 0
            for keyword in category.keywords:
                if keyword.lower() in search_text:
                    score += len(keyword)

            if score > best_score:
                best_score = score
                best_match = category

        # Income / expense without a keyword match still get a sensible default.
        if best_match is None and transaction_type == "income":
            return Category.objects.filter(
                is_system=True, name="Other Income"
            ).first()
        if best_match is None and transaction_type == "expense":
            return Category.objects.filter(
                is_system=True, name="Others"
            ).first()

        return best_match

    @staticmethod
    def refresh_system_keywords():
        """Push SYSTEM_CATEGORIES keyword updates onto existing DB rows."""
        updated = 0
        for cat_data in SYSTEM_CATEGORIES:
            n = Category.objects.filter(
                name=cat_data["name"], is_system=True
            ).update(keywords=cat_data["keywords"])
            updated += n
        return updated

    @staticmethod
    def categorize_uncategorized(user=None, limit: int | None = None) -> int:
        """Assign categories to transactions that have none."""
        from transactions.models import Transaction, TransactionType

        qs = Transaction.objects.filter(category__isnull=True).select_related(
            "user"
        )
        if user is not None:
            qs = qs.filter(user=user)
        if limit:
            qs = qs[:limit]

        count = 0
        for txn in qs.iterator(chunk_size=200):
            hint = (
                "income"
                if txn.transaction_type
                in (TransactionType.INCOME, TransactionType.RECURRING_INCOME)
                else "expense"
                if txn.transaction_type
                in (
                    TransactionType.EXPENSE,
                    TransactionType.RECURRING_EXPENSE,
                    TransactionType.EMI,
                )
                else None
            )
            cat = CategoryService.auto_categorize(
                txn.merchant_name or "",
                txn.description or "",
                transaction_type=hint,
            )
            if cat:
                txn.category = cat
                txn.save(update_fields=["category", "updated_at"])
                count += 1
        return count

    @staticmethod
    def seed_system_categories():
        """
        Seed default system categories if they don't exist.
        Called during migration or management command.
        """
        created_count = 0
        for i, cat_data in enumerate(SYSTEM_CATEGORIES):
            _, created = Category.objects.get_or_create(
                name=cat_data["name"],
                is_system=True,
                defaults={
                    "icon": cat_data["icon"],
                    "color": cat_data["color"],
                    "category_type": cat_data["category_type"],
                    "keywords": cat_data["keywords"],
                    "sort_order": i,
                },
            )
            if created:
                created_count += 1

        logger.info("Seeded %d system categories", created_count)
        return created_count


# Fix the import at the top that's needed for Q objects
from django.db import models  # noqa: E402
