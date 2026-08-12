"""
Users serializers — API data validation and transformation.
"""

from rest_framework import serializers

from users.models import Currency, User, UserProfile


class CurrencySerializer(serializers.ModelSerializer):
    class Meta:
        model = Currency
        fields = ["id", "code", "name", "symbol", "exchange_rate_to_usd"]


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = [
            "monthly_income",
            "financial_goal",
            "dashboard_layout",
            "notification_preferences",
        ]


class UserSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(read_only=True)
    default_currency = CurrencySerializer(read_only=True)
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "avatar",
            "phone",
            "timezone",
            "default_currency",
            "is_onboarded",
            "profile",
            "date_joined",
        ]
        read_only_fields = ["id", "email", "date_joined"]


class UserUpdateSerializer(serializers.ModelSerializer):
    default_currency = serializers.PrimaryKeyRelatedField(
        queryset=Currency.objects.filter(is_active=True),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = User
        fields = [
            "first_name",
            "last_name",
            "phone",
            "timezone",
            "default_currency",
        ]


class OnboardingSerializer(serializers.Serializer):
    currency_code = serializers.CharField(max_length=3)
    monthly_income = serializers.DecimalField(
        max_digits=15, decimal_places=2, required=False
    )

    def validate_currency_code(self, value):
        if not Currency.objects.filter(code=value.upper()).exists():
            raise serializers.ValidationError(f"Currency '{value}' is not supported.")
        return value.upper()


class ProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = [
            "monthly_income",
            "financial_goal",
            "dashboard_layout",
            "notification_preferences",
        ]
