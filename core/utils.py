"""
Core utilities — encryption, currency helpers, and common functions.
"""

import base64
import logging
from decimal import Decimal, InvalidOperation

from cryptography.fernet import Fernet
from django.conf import settings

logger = logging.getLogger("finsight")

# ---------------------------------------------------------------------------
# Encryption for sensitive fields (account numbers, etc.)
# ---------------------------------------------------------------------------
_fernet = None


def _get_fernet():
    """Lazily initialize Fernet cipher with the configured key."""
    global _fernet
    if _fernet is None:
        key = settings.FIELD_ENCRYPTION_KEY
        if not key:
            # Generate a key for development if not configured
            key = Fernet.generate_key().decode()
            logger.warning(
                "FIELD_ENCRYPTION_KEY not configured. Using auto-generated key. "
                "Set FIELD_ENCRYPTION_KEY in production!"
            )
        else:
            # Ensure the key is properly encoded
            if isinstance(key, str):
                try:
                    base64.urlsafe_b64decode(key)
                except Exception:
                    key = base64.urlsafe_b64encode(key.encode()[:32].ljust(32, b"\0")).decode()
        _fernet = Fernet(key if isinstance(key, bytes) else key.encode())
    return _fernet


def encrypt_field(value: str) -> str:
    """Encrypt a string value for storage."""
    if not value:
        return value
    f = _get_fernet()
    return f.encrypt(value.encode()).decode()


def decrypt_field(encrypted_value: str) -> str:
    """Decrypt an encrypted string value."""
    if not encrypted_value:
        return encrypted_value
    f = _get_fernet()
    return f.decrypt(encrypted_value.encode()).decode()


def mask_account_number(account_number: str) -> str:
    """
    Mask an account number, showing only the last 4 digits.

    Examples:
        '1234567890' -> '******7890'
        '4532' -> '4532'
    """
    if not account_number:
        return ""
    if len(account_number) <= 4:
        return account_number
    return "*" * (len(account_number) - 4) + account_number[-4:]


# ---------------------------------------------------------------------------
# Currency helpers
# ---------------------------------------------------------------------------

def to_decimal(value, default=Decimal("0.00")) -> Decimal:
    """Safely convert a value to Decimal."""
    if value is None:
        return default
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return default


def format_currency(amount: Decimal, currency_code: str = "USD", symbol: str = "$") -> str:
    """Format a decimal amount with currency symbol."""
    if amount < 0:
        return f"-{symbol}{abs(amount):,.2f}"
    return f"{symbol}{amount:,.2f}"


# ---------------------------------------------------------------------------
# General helpers
# ---------------------------------------------------------------------------

def get_client_ip(request) -> str:
    """Extract the client IP address from a request."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")
