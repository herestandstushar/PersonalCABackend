"""
Authentication services — JWT issuance, Google OAuth, token management.
"""

import logging

import requests
from django.conf import settings
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken

from core.exceptions import ServiceError, ValidationError
from users.services import UserService

logger = logging.getLogger("finsight")

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"


class AuthService:
    """Service layer for authentication operations."""

    @staticmethod
    def login(email: str, password: str) -> dict:
        """
        Authenticate user with email/password and return JWT tokens.

        Returns:
            Dict with access, refresh tokens and user data.

        Raises:
            ValidationError: If credentials are invalid.
        """
        user = authenticate(email=email, password=password)
        if user is None:
            raise ValidationError("Invalid email or password.")

        if not user.is_active:
            raise ValidationError("This account has been deactivated.")

        tokens = AuthService._generate_tokens(user)
        logger.info("User logged in: %s", user.email)
        return {
            "user": {
                "id": str(user.id),
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "full_name": user.full_name,
                "is_onboarded": user.is_onboarded,
            },
            **tokens,
        }

    @staticmethod
    def register(email: str, password: str, first_name: str, last_name: str = "") -> dict:
        """
        Register a new user and return JWT tokens.

        Returns:
            Dict with access, refresh tokens and user data.
        """
        from users.models import User

        if User.objects.filter(email=email).exists():
            raise ValidationError("An account with this email already exists.")

        user = UserService.create_user(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
        )

        tokens = AuthService._generate_tokens(user)
        logger.info("User registered: %s", user.email)
        return {
            "user": {
                "id": str(user.id),
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "full_name": user.full_name,
                "is_onboarded": user.is_onboarded,
            },
            **tokens,
        }

    @staticmethod
    def google_login(code: str = None, access_token: str = None) -> dict:
        """
        Authenticate via Google OAuth.

        Accepts either an authorization code (to exchange for tokens)
        or a direct access token (from frontend Google Sign-In).

        Returns:
            Dict with access, refresh tokens and user data.
        """
        if code:
            # Exchange authorization code for access token
            token_data = {
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": "postmessage",
                "grant_type": "authorization_code",
            }
            token_response = requests.post(GOOGLE_TOKEN_URL, data=token_data, timeout=10)
            if token_response.status_code != 200:
                raise ServiceError("Failed to exchange Google authorization code.")
            access_token = token_response.json().get("access_token")

        if not access_token:
            raise ValidationError("Google access token is required.")

        # Get user info from Google
        headers = {"Authorization": f"Bearer {access_token}"}
        user_response = requests.get(GOOGLE_USERINFO_URL, headers=headers, timeout=10)
        if user_response.status_code != 200:
            raise ServiceError("Failed to retrieve Google user information.")

        google_data = user_response.json()
        google_id = google_data.get("id")
        email = google_data.get("email")
        first_name = google_data.get("given_name", "")
        last_name = google_data.get("family_name", "")

        if not google_id or not email:
            raise ServiceError("Invalid Google user data.")

        user, created = UserService.create_or_get_google_user(
            google_id=google_id,
            email=email,
            first_name=first_name,
            last_name=last_name,
        )

        tokens = AuthService._generate_tokens(user)
        logger.info("Google login: %s (created=%s)", user.email, created)
        return {
            "user": {
                "id": str(user.id),
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "full_name": user.full_name,
                "is_onboarded": user.is_onboarded,
            },
            "is_new_user": created,
            **tokens,
        }

    @staticmethod
    def refresh_token(refresh: str) -> dict:
        """
        Refresh an access token using a valid refresh token.

        Returns:
            Dict with new access and refresh tokens.
        """
        try:
            token = RefreshToken(refresh)
            return {
                "access": str(token.access_token),
                "refresh": str(token),
            }
        except Exception as e:
            raise ValidationError(f"Invalid or expired refresh token: {e}")

    @staticmethod
    def logout(refresh: str):
        """Blacklist the refresh token to log the user out."""
        try:
            token = RefreshToken(refresh)
            token.blacklist()
        except Exception:
            pass  # Token may already be blacklisted or invalid

    @staticmethod
    def _generate_tokens(user) -> dict:
        """Generate access and refresh JWT tokens for a user."""
        refresh = RefreshToken.for_user(user)
        return {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        }
