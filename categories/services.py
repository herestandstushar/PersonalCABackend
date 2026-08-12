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
    def auto_categorize(merchant_name: str, description: str = "") -> Category | None:
        """
        Auto-categorize a transaction based on merchant name and description.

        Uses keyword matching against system categories.

        Returns:
            Matching Category or None if no match found.
        """
        if not merchant_name and not description:
            return None

        search_text = f"{merchant_name} {description}".lower()

        # Try to match against system category keywords
        system_categories = Category.objects.filter(is_system=True).exclude(
            keywords=[]
        )

        best_match = None
        best_score = 0

        for category in system_categories:
            score = 0
            for keyword in category.keywords:
                if keyword.lower() in search_text:
                    # Longer keyword matches get higher score
                    score += len(keyword)

            if score > best_score:
                best_score = score
                best_match = category

        return best_match

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
