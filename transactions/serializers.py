"""
Transactions serializers.
"""

from rest_framework import serializers

from accounts.models import Account
from categories.models import Category
from transactions.models import Transaction, TransactionType
from users.models import Currency


class CategoryBriefSerializer(serializers.ModelSerializer):
    """Minimal category payload for nested list/detail embeds."""

    class Meta:
        model = Category
        fields = ["id", "name", "icon", "color", "category_type"]


class AccountBriefSerializer(serializers.ModelSerializer):
    """Minimal account payload — avoids decrypting numbers on every list row."""

    class Meta:
        model = Account
        fields = ["id", "name", "account_type", "color", "icon"]


class TransactionListSerializer(serializers.ModelSerializer):
    """Lean list serializer for fast table loads."""

    category_detail = CategoryBriefSerializer(source="category", read_only=True)
    account_detail = AccountBriefSerializer(source="account", read_only=True)
    is_credit = serializers.BooleanField(read_only=True)
    is_debit = serializers.BooleanField(read_only=True)

    class Meta:
        model = Transaction
        fields = [
            "id",
            "transaction_type",
            "amount",
            "currency",
            "date",
            "merchant_name",
            "description",
            "category",
            "category_detail",
            "account",
            "account_detail",
            "payment_method",
            "source",
            "is_credit",
            "is_debit",
            "created_at",
        ]


class TransactionSerializer(serializers.ModelSerializer):
    """Full read serializer for single-transaction views / edits."""

    category_detail = CategoryBriefSerializer(source="category", read_only=True)
    account_detail = AccountBriefSerializer(source="account", read_only=True)
    is_credit = serializers.BooleanField(read_only=True)
    is_debit = serializers.BooleanField(read_only=True)

    class Meta:
        model = Transaction
        fields = [
            "id",
            "transaction_type",
            "amount",
            "currency",
            "exchange_rate",
            "date",
            "time",
            "merchant_name",
            "description",
            "notes",
            "category",
            "category_detail",
            "account",
            "account_detail",
            "to_account",
            "payment_method",
            "tags",
            "source",
            "is_recurring",
            "is_duplicate",
            "is_credit",
            "is_debit",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "source", "is_duplicate", "created_at", "updated_at"]


class TransactionCreateSerializer(serializers.ModelSerializer):
    """Write serializer for creating/updating transactions."""

    currency = serializers.PrimaryKeyRelatedField(
        queryset=Currency.objects.all(),
        required=False,
        allow_null=True,
        help_text="Defaults to the source account's currency when omitted.",
    )

    class Meta:
        model = Transaction
        fields = [
            "id",
            "transaction_type",
            "amount",
            "currency",
            "exchange_rate",
            "date",
            "time",
            "merchant_name",
            "description",
            "notes",
            "category",
            "account",
            "to_account",
            "payment_method",
            "tags",
            "is_recurring",
        ]
        read_only_fields = ["id"]

    def validate(self, attrs):
        txn_type = attrs.get("transaction_type")

        if txn_type == TransactionType.TRANSFER:
            if not attrs.get("to_account"):
                raise serializers.ValidationError(
                    {"to_account": "Destination account is required for transfers."}
                )
            if attrs.get("account") == attrs.get("to_account"):
                raise serializers.ValidationError(
                    {"to_account": "Source and destination accounts must be different."}
                )

        if attrs.get("amount") and attrs["amount"] <= 0:
            raise serializers.ValidationError(
                {"amount": "Amount must be positive."}
            )

        return attrs


class TransactionBulkSerializer(serializers.Serializer):
    """Serializer for bulk importing transactions from statements."""

    transactions = TransactionCreateSerializer(many=True)


class SpendingSummarySerializer(serializers.Serializer):
    today = serializers.DecimalField(max_digits=15, decimal_places=2)
    this_week = serializers.DecimalField(max_digits=15, decimal_places=2)
    this_month = serializers.DecimalField(max_digits=15, decimal_places=2)
    this_year = serializers.DecimalField(max_digits=15, decimal_places=2)
