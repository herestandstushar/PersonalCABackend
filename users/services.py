"""
Users services — business logic for user management.
"""

import logging

from django.db import transaction

from users.models import Currency, User, UserProfile

logger = logging.getLogger("finsight")


class UserService:
    """Service layer for user-related operations."""

    @staticmethod
    @transaction.atomic
    def create_user(
        email: str,
        password: str,
        first_name: str,
        last_name: str = "",
        **kwargs,
    ) -> User:
        """
        Create a new user and associated profile.

        Args:
            email: User's email address
            password: Plain text password (will be hashed)
            first_name: User's first name
            last_name: User's last name

        Returns:
            Created User instance
        """
        user = User.objects.create_user(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            **kwargs,
        )
        UserProfile.objects.create(user=user)
        logger.info("Created user: %s", user.email)
        return user

    @staticmethod
    @transaction.atomic
    def create_or_get_google_user(
        google_id: str,
        email: str,
        first_name: str,
        last_name: str = "",
        avatar_url: str = "",
    ) -> tuple[User, bool]:
        """
        Get or create a user from Google OAuth data.

        Returns:
            Tuple of (User, created: bool)
        """
        try:
            user = User.objects.get(google_id=google_id)
            return user, False
        except User.DoesNotExist:
            pass

        # Check if email already exists (user registered via email, now linking Google)
        try:
            user = User.objects.get(email__iexact=email)
            user.google_id = google_id
            if user.email != email:
                user.email = email
                user.save(update_fields=["google_id", "email"])
            else:
                user.save(update_fields=["google_id"])
            return user, False
        except User.DoesNotExist:
            pass

        user = User.objects.create_user(
            email=email,
            password=None,  # No password for OAuth users
            first_name=first_name,
            last_name=last_name,
            google_id=google_id,
        )
        UserProfile.objects.create(user=user)
        logger.info("Created Google user: %s", user.email)
        return user, True

    @staticmethod
    def update_profile(user: User, **data) -> UserProfile:
        """Update user profile with given data."""
        profile, _ = UserProfile.objects.get_or_create(user=user)
        for key, value in data.items():
            if hasattr(profile, key):
                setattr(profile, key, value)
        profile.save()
        return profile

    @staticmethod
    def complete_onboarding(user: User, currency_code: str, monthly_income=None):
        """Mark user as onboarded and set initial preferences."""
        try:
            currency = Currency.objects.get(code=currency_code.upper())
            user.default_currency = currency
        except Currency.DoesNotExist:
            pass

        user.is_onboarded = True
        user.save(update_fields=["default_currency", "is_onboarded"])

        if monthly_income is not None:
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.monthly_income = monthly_income
            profile.save(update_fields=["monthly_income"])

        return user

    @staticmethod
    def get_user_with_profile(user_id) -> User:
        """Fetch user with profile prefetched."""
        return User.objects.select_related("profile", "default_currency").get(
            id=user_id
        )
