"""
Accounts serializers.
"""

from rest_framework import serializers

from accounts.models import Account, AccountType
from accounts.services import AccountService
from users.models import Currency
from users.serializers import CurrencySerializer


class AccountSerializer(serializers.ModelSerializer):
    """Read serializer — includes masked account number and computed fields."""

    currency_detail = CurrencySerializer(source="currency", read_only=True)
    masked_account_number = serializers.SerializerMethodField()
    available_credit = serializers.DecimalField(
        max_digits=15, decimal_places=2, read_only=True
    )
    credit_utilization = serializers.FloatField(read_only=True)

    class Meta:
        model = Account
        fields = [
            "id",
            "name",
            "account_type",
            "bank_name",
            "masked_account_number",
            "currency",
            "currency_detail",
            "current_balance",
            "credit_limit",
            "available_credit",
            "credit_utilization",
            "color",
            "icon",
            "is_active",
            "is_default",
            "last_synced",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "current_balance"]

    def get_masked_account_number(self, obj):
        return AccountService.get_masked_account_number(obj)


class AccountCreateSerializer(serializers.ModelSerializer):
    """Write serializer — validates account creation data."""

    account_number = serializers.CharField(required=False, write_only=True)
    currency = serializers.PrimaryKeyRelatedField(
        queryset=Currency.objects.all(),
        required=False,
        allow_null=True,
        help_text="Defaults to the user's preferred currency when omitted.",
    )

    class Meta:
        model = Account
        fields = [
            "id",
            "name",
            "account_type",
            "bank_name",
            "account_number",
            "currency",
            "current_balance",
            "credit_limit",
            "color",
            "icon",
            "is_default",
            "notes",
        ]
        read_only_fields = ["id"]

    def validate(self, attrs):
        if attrs.get("account_type") == AccountType.CREDIT_CARD:
            if not attrs.get("credit_limit"):
                raise serializers.ValidationError(
                    {"credit_limit": "Credit limit is required for credit cards."}
                )
        return attrs


class AccountSummarySerializer(serializers.Serializer):
    """Serializer for account balance summary."""

    total_assets = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_liabilities = serializers.DecimalField(max_digits=15, decimal_places=2)
    net_worth = serializers.DecimalField(max_digits=15, decimal_places=2)
