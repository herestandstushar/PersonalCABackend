"""
Authentication serializers — request validation.
"""

from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150, required=False, default="")

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError(
                {"password_confirm": "Passwords do not match."}
            )
        return attrs


class GoogleAuthSerializer(serializers.Serializer):
    code = serializers.CharField(required=False)
    access_token = serializers.CharField(required=False)

    def validate(self, attrs):
        if not attrs.get("code") and not attrs.get("access_token"):
            raise serializers.ValidationError(
                "Either 'code' or 'access_token' must be provided."
            )
        return attrs


class TokenRefreshSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()
