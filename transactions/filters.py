"""
Transactions filters — advanced Django-filter integration.
"""

import django_filters

from transactions.models import Transaction, TransactionType, PaymentMethod


class TransactionFilter(django_filters.FilterSet):
    """Advanced filtering for transactions list."""

    date_from = django_filters.DateFilter(field_name="date", lookup_expr="gte")
    date_to = django_filters.DateFilter(field_name="date", lookup_expr="lte")
    amount_min = django_filters.NumberFilter(field_name="amount", lookup_expr="gte")
    amount_max = django_filters.NumberFilter(field_name="amount", lookup_expr="lte")
    merchant = django_filters.CharFilter(
        field_name="merchant_name", lookup_expr="icontains"
    )
    transaction_type = django_filters.ChoiceFilter(choices=TransactionType.choices)
    payment_method = django_filters.ChoiceFilter(choices=PaymentMethod.choices)
    category = django_filters.UUIDFilter(field_name="category_id")
    account = django_filters.UUIDFilter(field_name="account_id")
    search = django_filters.CharFilter(method="filter_search")
    is_recurring = django_filters.BooleanFilter()

    class Meta:
        model = Transaction
        fields = [
            "date_from",
            "date_to",
            "amount_min",
            "amount_max",
            "merchant",
            "transaction_type",
            "payment_method",
            "category",
            "account",
            "search",
            "is_recurring",
        ]

    def filter_search(self, queryset, name, value):
        """Full-text search across merchant, description, and notes."""
        from django.db.models import Q

        return queryset.filter(
            Q(merchant_name__icontains=value)
            | Q(description__icontains=value)
            | Q(notes__icontains=value)
        )
