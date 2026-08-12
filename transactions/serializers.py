"""
Transactions serializers.
"""

from rest_framework import serializers

from accounts.serializers import AccountSerializer
from categories.serializers import CategorySerializer
from transactions.models import Transaction, TransactionType
from users.models import Currency


class TransactionSerializer(serializers.ModelSerializer):
    """Read serializer with nested category and account details."""

    category_detail = CategorySerializer(source="category", read_only=True)
    account_detail = AccountSerializer(source="account", read_only=True)
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
