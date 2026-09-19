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
    has_statement_password = serializers.SerializerMethodField()
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
            "has_statement_password",
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

    def get_has_statement_password(self, obj):
        return bool(obj.statement_password_encrypted)


class AccountCreateSerializer(serializers.ModelSerializer):
    """Write serializer — validates account creation data."""

    account_number = serializers.CharField(required=False, write_only=True)
    statement_password = serializers.CharField(
        required=False,
        allow_blank=True,
        write_only=True,
        help_text="PDF statement password — stored encrypted; never returned.",
    )
    clear_statement_password = serializers.BooleanField(
        required=False,
        write_only=True,
        default=False,
        help_text="Set true to remove the saved statement password.",
    )
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
            "statement_password",
            "clear_statement_password",
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
        account_type = attrs.get("account_type")
        credit_limit = attrs.get("credit_limit")
        # On PATCH, fall back to the existing row so partial updates don't fail.
        if self.instance is not None:
            account_type = account_type or self.instance.account_type
            if credit_limit is None:
                credit_limit = self.instance.credit_limit

        if account_type == AccountType.CREDIT_CARD and not credit_limit:
            raise serializers.ValidationError(
                {"credit_limit": "Credit limit is required for credit cards."}
            )

        balance = attrs.get("current_balance")
        if (
            account_type == AccountType.CREDIT_CARD
            and balance is not None
            and credit_limit is not None
            and balance > credit_limit
        ):
            raise serializers.ValidationError(
                {
                    "current_balance": "Outstanding usage cannot exceed the credit limit."
                }
            )
        return attrs


class AccountSummarySerializer(serializers.Serializer):
    """Serializer for account balance summary."""

    total_assets = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_liabilities = serializers.DecimalField(max_digits=15, decimal_places=2)
    net_worth = serializers.DecimalField(max_digits=15, decimal_places=2)
