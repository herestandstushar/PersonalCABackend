"""
Users models — Custom User, UserProfile, and Currency.
"""

import uuid

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    """Custom user manager that uses email as the unique identifier."""

    def normalize_email(self, email):
        """Lowercase the entire address — login is case-insensitive."""
        email = super().normalize_email(email or "")
        return email.strip().lower()

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """
    Custom User model with email as the primary login field.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = None  # Remove username field
    email = models.EmailField(unique=True, db_index=True)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150, blank=True)
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True)
    timezone = models.CharField(max_length=50, default="UTC")
    default_currency = models.ForeignKey(
        "Currency",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users",
    )
    google_id = models.CharField(max_length=255, blank=True, null=True, unique=True)
    is_onboarded = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name"]

    class Meta:
        db_table = "users"
        verbose_name = "User"
        verbose_name_plural = "Users"

    def __str__(self):
        return self.email

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()


class UserProfile(models.Model):
    """
    Extended user profile for preferences and dashboard customization.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    monthly_income = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    financial_goal = models.CharField(max_length=255, blank=True)
    dashboard_layout = models.JSONField(
        default=dict,
        blank=True,
        help_text="JSON configuration for dashboard widget layout",
    )
    notification_preferences = models.JSONField(
        default=dict,
        blank=True,
        help_text="Notification channel preferences",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "user_profiles"

    def __str__(self):
        return f"Profile: {self.user.email}"


class Currency(models.Model):
    """
    Supported currencies with exchange rates.
    """

    code = models.CharField(max_length=3, unique=True, db_index=True)
    name = models.CharField(max_length=100)
    symbol = models.CharField(max_length=10)
    exchange_rate_to_usd = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        default=1.0,
        help_text="Exchange rate relative to USD",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "currencies"
        verbose_name_plural = "Currencies"
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} ({self.symbol})"
