"""
Categories models — transaction categorization with icons and colors.
"""

from django.conf import settings
from django.db import models

from core.models import BaseModel


class CategoryType(models.TextChoices):
    EXPENSE = "expense", "Expense"
    INCOME = "income", "Income"
    TRANSFER = "transfer", "Transfer"


class Category(BaseModel):
    """
    Transaction category with icon, color, and optional hierarchy.
    """

    name = models.CharField(max_length=100)
    icon = models.CharField(max_length=50, default="tag", help_text="Lucide icon name")
    color = models.CharField(max_length=7, default="#6366f1", help_text="Hex color")
    category_type = models.CharField(
        max_length=20,
        choices=CategoryType.choices,
        default=CategoryType.EXPENSE,
        db_index=True,
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subcategories",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="custom_categories",
        help_text="Null for system (default) categories",
    )
    is_system = models.BooleanField(
        default=False,
        help_text="System categories are available to all users",
    )
    keywords = models.JSONField(
        default=list,
        blank=True,
        help_text="Keywords for auto-categorization matching",
    )
    sort_order = models.IntegerField(default=0)

    class Meta:
        db_table = "categories"
        verbose_name_plural = "Categories"
        ordering = ["sort_order", "name"]
        indexes = [
            models.Index(fields=["user", "category_type"]),
            models.Index(fields=["is_system"]),
        ]

    def __str__(self):
        return self.name


# Default system categories — seeded via data migration
SYSTEM_CATEGORIES = [
    # Expenses
    {"name": "Food & Dining", "icon": "utensils", "color": "#f97316", "category_type": "expense", "keywords": ["restaurant", "food", "dining", "cafe", "coffee"]},
    {"name": "Groceries", "icon": "shopping-cart", "color": "#22c55e", "category_type": "expense", "keywords": ["grocery", "supermarket", "mart", "vegetables", "fruits"]},
    {"name": "Fuel", "icon": "fuel", "color": "#ef4444", "category_type": "expense", "keywords": ["petrol", "diesel", "fuel", "gas station", "petroleum"]},
    {"name": "Travel", "icon": "plane", "color": "#3b82f6", "category_type": "expense", "keywords": ["flight", "hotel", "travel", "booking", "airline", "train", "cab", "uber", "ola"]},
    {"name": "Shopping", "icon": "shopping-bag", "color": "#a855f7", "category_type": "expense", "keywords": ["amazon", "flipkart", "shopping", "myntra", "mall"]},
    {"name": "Rent", "icon": "home", "color": "#06b6d4", "category_type": "expense", "keywords": ["rent", "housing", "apartment"]},
    {"name": "Utilities", "icon": "zap", "color": "#eab308", "category_type": "expense", "keywords": ["electricity", "water", "gas", "utility", "bill"]},
    {"name": "Medical", "icon": "heart-pulse", "color": "#ec4899", "category_type": "expense", "keywords": ["hospital", "doctor", "pharmacy", "medical", "health", "medicine"]},
    {"name": "Entertainment", "icon": "film", "color": "#8b5cf6", "category_type": "expense", "keywords": ["movie", "netflix", "spotify", "entertainment", "gaming"]},
    {"name": "Insurance", "icon": "shield", "color": "#14b8a6", "category_type": "expense", "keywords": ["insurance", "premium", "policy", "lic"]},
    {"name": "Education", "icon": "graduation-cap", "color": "#0ea5e9", "category_type": "expense", "keywords": ["school", "college", "course", "education", "tuition", "book"]},
    {"name": "EMI", "icon": "calculator", "color": "#f43f5e", "category_type": "expense", "keywords": ["emi", "installment", "loan payment"]},
    {"name": "Tax", "icon": "receipt", "color": "#64748b", "category_type": "expense", "keywords": ["tax", "income tax", "gst", "tds"]},
    {"name": "Subscriptions", "icon": "repeat", "color": "#d946ef", "category_type": "expense", "keywords": ["subscription", "membership", "recurring"]},
    {"name": "Personal Care", "icon": "sparkles", "color": "#f472b6", "category_type": "expense", "keywords": ["salon", "spa", "grooming", "beauty"]},
    {"name": "Gifts & Donations", "icon": "gift", "color": "#fb923c", "category_type": "expense", "keywords": ["gift", "donation", "charity"]},
    {"name": "Investment", "icon": "trending-up", "color": "#10b981", "category_type": "expense", "keywords": ["mutual fund", "stock", "sip", "invest"]},
    {"name": "Others", "icon": "more-horizontal", "color": "#94a3b8", "category_type": "expense", "keywords": []},
    # Income
    {"name": "Salary", "icon": "banknote", "color": "#22c55e", "category_type": "income", "keywords": ["salary", "payroll", "wages"]},
    {"name": "Freelance", "icon": "laptop", "color": "#3b82f6", "category_type": "income", "keywords": ["freelance", "contract", "consulting"]},
    {"name": "Interest", "icon": "percent", "color": "#06b6d4", "category_type": "income", "keywords": ["interest", "fd", "savings interest"]},
    {"name": "Dividend", "icon": "bar-chart-3", "color": "#8b5cf6", "category_type": "income", "keywords": ["dividend"]},
    {"name": "Rental Income", "icon": "building", "color": "#f97316", "category_type": "income", "keywords": ["rental", "rent received"]},
    {"name": "Refund", "icon": "rotate-ccw", "color": "#14b8a6", "category_type": "income", "keywords": ["refund", "cashback", "return"]},
    {"name": "Other Income", "icon": "plus-circle", "color": "#94a3b8", "category_type": "income", "keywords": []},
    # Transfer
    {"name": "Transfer", "icon": "arrow-left-right", "color": "#6366f1", "category_type": "transfer", "keywords": ["transfer", "moved"]},
]
