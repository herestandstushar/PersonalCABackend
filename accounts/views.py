"""
Accounts views — thin controllers.
"""

from rest_framework import permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from accounts.models import Account
from accounts.serializers import (
    AccountCreateSerializer,
    AccountSerializer,
    AccountSummarySerializer,
)
from accounts.services import AccountService
from core.permissions import IsOwner


class AccountViewSet(ModelViewSet):
    """
    CRUD operations for financial accounts.

    GET    /accounts/          — List user's accounts
    POST   /accounts/          — Create new account
    GET    /accounts/{id}/     — Get account details
    PATCH  /accounts/{id}/     — Update account
    DELETE /accounts/{id}/     — Soft-delete account
    POST   /accounts/{id}/reset/ — Clear history for one account
    POST   /accounts/reset-all/  — Clear history for all accounts
    GET    /accounts/summary/  — Get balance summary
    """

    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return AccountCreateSerializer
        return AccountSerializer

    def get_queryset(self):
        return AccountService.get_user_accounts(
            user=self.request.user,
            account_type=self.request.query_params.get("type"),
            is_active=self.request.query_params.get("is_active"),
        )

    def perform_create(self, serializer):
        data = serializer.validated_data.copy()
        AccountService.create_account(user=self.request.user, data=data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data.copy()
        account = AccountService.create_account(user=request.user, data=data)
        return Response(
            AccountSerializer(account).data,
            status=status.HTTP_201_CREATED,
        )

    def perform_update(self, serializer):
        data = serializer.validated_data.copy()
        AccountService.update_account(
            user=self.request.user,
            account_id=self.kwargs["pk"],
            data=data,
        )

    def perform_destroy(self, instance):
        AccountService.delete_account(
            user=self.request.user,
            account_id=instance.id,
        )

    @action(detail=True, methods=["post"])
    def reset(self, request, pk=None):
        """POST /accounts/{id}/reset/ — Clear transactions & statements; zero balance."""
        result = AccountService.reset_account(request.user, pk)
        return Response(result)

    @action(detail=False, methods=["post"], url_path="reset-all")
    def reset_all(self, request):
        """POST /accounts/reset-all/ — Clear history for every account."""
        result = AccountService.reset_all_accounts(request.user)
        return Response(result)

    @action(detail=False, methods=["get"])
    def summary(self, request):
        """GET /accounts/summary/ — Total balance summary across all accounts."""
        data = AccountService.get_total_balance(request.user)
        serializer = AccountSummarySerializer(data)
        return Response(serializer.data)
