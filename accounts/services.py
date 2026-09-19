"""
Accounts services — business logic for financial accounts.
"""

import logging
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from accounts.models import Account, AccountType
from core.exceptions import NotFoundError, ValidationError
from core.utils import decrypt_field, encrypt_field, mask_account_number

logger = logging.getLogger("finsight")


class AccountService:
    """Service layer for account management."""

    @staticmethod
    @transaction.atomic
    def create_account(user, data: dict) -> Account:
        """
        Create a new financial account.

        Encrypts account number if provided.
        Sets as default if it's the user's first account.
        """
        account_number = data.pop("account_number", None)
        encrypted_number = ""
        if account_number:
            encrypted_number = encrypt_field(account_number)

        statement_password = data.pop("statement_password", None)
        data.pop("clear_statement_password", None)
        encrypted_stmt_pw = ""
        if statement_password:
            encrypted_stmt_pw = encrypt_field(statement_password)

        # Fall back to the user's preferred currency so clients need not send one
        if not data.get("currency"):
            currency = user.default_currency
            if currency is None:
                from users.models import Currency

                currency = Currency.objects.filter(code="USD").first()
            if currency is None:
                raise ValidationError(
                    "No currency available. Seed currencies before creating accounts."
                )
            data["currency"] = currency

        # If this is the user's first account, make it default
        is_first = not Account.objects.filter(user=user).exists()
        if is_first:
            data.setdefault("is_default", True)

        # If setting as default, un-default others
        if data.get("is_default"):
            Account.objects.filter(user=user, is_default=True).update(is_default=False)

        account = Account.objects.create(
            user=user,
            account_number_encrypted=encrypted_number,
            statement_password_encrypted=encrypted_stmt_pw,
            **data,
        )

        logger.info("Account created: %s for user %s", account.name, user.email)
        return account

    @staticmethod
    def get_account(user, account_id) -> Account:
        """Get a single account owned by the user."""
        try:
            return Account.objects.select_related("currency").get(
                id=account_id, user=user
            )
        except Account.DoesNotExist:
            raise NotFoundError("Account not found.")

    @staticmethod
    def get_user_accounts(user, account_type=None, is_active=None):
        """Get all accounts for a user with optional filters."""
        qs = Account.objects.filter(user=user).select_related("currency")
        if account_type:
            qs = qs.filter(account_type=account_type)
        if is_active is not None:
            qs = qs.filter(is_active=is_active)
        return qs

    @staticmethod
    @transaction.atomic
    def update_balance(account: Account, amount: Decimal, is_credit: bool = True):
        """
        Atomically update account balance.

        For credit cards, credits reduce balance (payments), debits increase it.
        For other accounts, credits increase balance, debits decrease it.
        """
        account.refresh_from_db()
        if is_credit:
            if account.account_type == AccountType.CREDIT_CARD:
                account.current_balance -= amount  # Payment reduces debt
            else:
                account.current_balance += amount
        else:
            if account.account_type == AccountType.CREDIT_CARD:
                account.current_balance += amount  # Purchase increases debt
            else:
                account.current_balance -= amount

        account.save(update_fields=["current_balance", "updated_at"])
        return account

    @staticmethod
    def get_total_balance(user) -> dict:
        """Calculate total balances across all active accounts."""
        accounts = Account.objects.filter(user=user, is_active=True)

        # Assets: bank_account + wallet + cash + upi
        asset_types = [
            AccountType.BANK_ACCOUNT,
            AccountType.WALLET,
            AccountType.CASH,
            AccountType.UPI,
        ]
        total_assets = (
            accounts.filter(account_type__in=asset_types).aggregate(
                total=Sum("current_balance")
            )["total"]
            or Decimal("0")
        )

        # Liabilities: credit card balance (debt)
        total_liabilities = (
            accounts.filter(account_type=AccountType.CREDIT_CARD).aggregate(
                total=Sum("current_balance")
            )["total"]
            or Decimal("0")
        )

        return {
            "total_assets": total_assets,
            "total_liabilities": total_liabilities,
            "net_worth": total_assets - total_liabilities,
        }

    @staticmethod
    def get_masked_account_number(account: Account) -> str:
        """Return masked account number for display."""
        if not account.account_number_encrypted:
            return ""
        try:
            decrypted = decrypt_field(account.account_number_encrypted)
            return mask_account_number(decrypted)
        except Exception:
            return "****"

    @staticmethod
    @transaction.atomic
    def update_account(user, account_id, data: dict) -> Account:
        """Update an existing account."""
        account = AccountService.get_account(user, account_id)

        account_number = data.pop("account_number", None)
        if account_number:
            account.account_number_encrypted = encrypt_field(account_number)

        clear_stmt_pw = data.pop("clear_statement_password", False)
        statement_password = data.pop("statement_password", None)
        if clear_stmt_pw:
            account.statement_password_encrypted = ""
        elif statement_password:
            account.statement_password_encrypted = encrypt_field(statement_password)

        if data.get("is_default"):
            Account.objects.filter(user=user, is_default=True).update(is_default=False)

        for key, value in data.items():
            if hasattr(account, key):
                setattr(account, key, value)

        account.save()
        return account

    @staticmethod
    def set_statement_password(account: Account, password: str) -> None:
        """Encrypt and store a PDF statement password on the account."""
        if not password:
            return
        account.statement_password_encrypted = encrypt_field(password)
        account.save(update_fields=["statement_password_encrypted", "updated_at"])

    @staticmethod
    def get_statement_password(account: Account) -> str:
        if not account.statement_password_encrypted:
            return ""
        try:
            return decrypt_field(account.statement_password_encrypted)
        except Exception:
            return ""

    @staticmethod
    @transaction.atomic
    def reset_account(user, account_id) -> dict:
        """
        Clear transaction/statement history for one account and zero its balance.
        Account itself is kept so it can be re-imported cleanly.
        """
        from django.db.models import Q
        from django.utils import timezone
        from statements.models import Statement
        from transactions.models import Transaction

        account = AccountService.get_account(user, account_id)
        now = timezone.now()

        txn_qs = Transaction.objects.filter(user=user).filter(
            Q(account=account) | Q(to_account=account)
        )
        transactions_cleared = txn_qs.count()
        txn_qs.update(is_deleted=True, updated_at=now)

        stmt_qs = Statement.objects.filter(user=user, account=account)
        statements_cleared = stmt_qs.count()
        stmt_qs.update(is_deleted=True, updated_at=now)

        account.current_balance = Decimal("0.00")
        account.save(update_fields=["current_balance", "updated_at"])

        logger.info(
            "Account reset: %s (%s txns, %s stmts) for user %s",
            account.name,
            transactions_cleared,
            statements_cleared,
            user.email,
        )
        return {
            "accounts_reset": 1,
            "transactions_cleared": transactions_cleared,
            "statements_cleared": statements_cleared,
        }

    @staticmethod
    @transaction.atomic
    def reset_all_accounts(user) -> dict:
        """Clear history for every account owned by the user."""
        from django.utils import timezone
        from statements.models import Statement
        from transactions.models import Transaction

        now = timezone.now()
        accounts = Account.objects.filter(user=user)
        accounts_reset = accounts.count()

        txn_qs = Transaction.objects.filter(user=user)
        transactions_cleared = txn_qs.count()
        txn_qs.update(is_deleted=True, updated_at=now)

        stmt_qs = Statement.objects.filter(user=user)
        statements_cleared = stmt_qs.count()
        stmt_qs.update(is_deleted=True, updated_at=now)

        accounts.update(current_balance=Decimal("0.00"), updated_at=now)

        logger.info(
            "All accounts reset (%s accounts, %s txns) for user %s",
            accounts_reset,
            transactions_cleared,
            user.email,
        )
        return {
            "accounts_reset": accounts_reset,
            "transactions_cleared": transactions_cleared,
            "statements_cleared": statements_cleared,
        }

    @staticmethod
    def delete_account(user, account_id):
        """Soft-delete an account."""
        account = AccountService.get_account(user, account_id)
        account.soft_delete()
        logger.info("Account deleted: %s for user %s", account.name, user.email)
