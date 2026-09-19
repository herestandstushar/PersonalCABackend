"""
Transactions views — thin controllers.
"""

from rest_framework import permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from core.permissions import IsOwner
from transactions.filters import TransactionFilter
from transactions.models import Transaction
from transactions.serializers import (
    SpendingSummarySerializer,
    TransactionBulkSerializer,
    TransactionCreateSerializer,
    TransactionListSerializer,
    TransactionSerializer,
)
from transactions.services import TransactionService


class TransactionViewSet(ModelViewSet):
    """
    CRUD for transactions with advanced filtering.

    GET    /transactions/                — List with filters
    POST   /transactions/               — Create transaction
    GET    /transactions/{id}/           — Get details
    PATCH  /transactions/{id}/           — Update
    DELETE /transactions/{id}/           — Soft-delete (reverses balance)
    POST   /transactions/bulk/           — Bulk import
    GET    /transactions/spending/       — Spending summary
    GET    /transactions/categories/     — Category breakdown
    GET    /transactions/merchants/      — Merchant breakdown
    GET    /transactions/cash-flow/      — Cash flow data
    GET    /transactions/daily/          — Daily spending
    GET    /transactions/top/            — Top largest expenses
    GET    /transactions/payment-methods/ — Payment method breakdown
    """

    permission_classes = [permissions.IsAuthenticated, IsOwner]
    filterset_class = TransactionFilter
    search_fields = ["merchant_name", "description", "notes"]
    ordering_fields = ["date", "amount", "created_at", "merchant_name"]
    ordering = ["-date", "-created_at"]

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return TransactionCreateSerializer
        if self.action == "list":
            return TransactionListSerializer
        return TransactionSerializer

    def get_queryset(self):
        qs = Transaction.for_user(self.request.user)
        if self.action == "list":
            # Skip currency/to_account joins — list serializer does not need them.
            return qs.select_related("category", "account")
        return qs.select_related("category", "account", "currency", "to_account")

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        txn = TransactionService.create_transaction(
            user=request.user,
            data=serializer.validated_data.copy(),
        )
        return Response(
            TransactionSerializer(txn).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, partial=kwargs.get("partial", False))
        serializer.is_valid(raise_exception=True)
        txn = TransactionService.update_transaction(
            user=request.user,
            txn_id=self.kwargs["pk"],
            data=serializer.validated_data.copy(),
        )
        return Response(TransactionSerializer(txn).data)

    def perform_destroy(self, instance):
        TransactionService.delete_transaction(
            user=self.request.user,
            txn_id=instance.id,
        )

    @action(detail=False, methods=["post"], url_path="bulk")
    def bulk_create(self, request):
        """POST /transactions/bulk/ — Bulk import transactions."""
        serializer = TransactionBulkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        txns = TransactionService.bulk_create_transactions(
            user=request.user,
            transactions_data=serializer.validated_data["transactions"],
        )
        return Response(
            TransactionSerializer(txns, many=True).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["get"])
    def spending(self, request):
        """GET /transactions/spending/ — Spending summary."""
        data = TransactionService.get_spending_summary(request.user)
        return Response(SpendingSummarySerializer(data).data)

    @action(detail=False, methods=["get"], url_path="categories")
    def category_breakdown(self, request):
        """GET /transactions/categories/ — Category breakdown."""
        data = TransactionService.get_category_breakdown(
            user=request.user,
            date_from=request.query_params.get("date_from"),
            date_to=request.query_params.get("date_to"),
        )
        return Response(data)

    @action(detail=False, methods=["get"], url_path="merchants")
    def merchant_breakdown(self, request):
        """GET /transactions/merchants/ — Merchant breakdown."""
        data = TransactionService.get_merchant_breakdown(
            user=request.user,
            date_from=request.query_params.get("date_from"),
            date_to=request.query_params.get("date_to"),
        )
        return Response(data)

    @action(detail=False, methods=["get"], url_path="cash-flow")
    def cash_flow(self, request):
        """GET /transactions/cash-flow/ — Monthly income vs expense."""
        months = int(request.query_params.get("months", 6))
        data = TransactionService.get_cash_flow(request.user, months=months)
        return Response(data)

    @action(detail=False, methods=["get"], url_path="daily")
    def daily_spending(self, request):
        """GET /transactions/daily/ — Daily spending chart data."""
        days = int(request.query_params.get("days", 30))
        data = TransactionService.get_daily_spending(request.user, days=days)
        return Response(data)

    @action(detail=False, methods=["get"], url_path="top")
    def top_expenses(self, request):
        """GET /transactions/top/ — Top N largest expenses."""
        limit = int(request.query_params.get("limit", 10))
        txns = TransactionService.get_top_transactions(request.user, limit=limit)
        return Response(TransactionSerializer(txns, many=True).data)

    @action(detail=False, methods=["get"], url_path="payment-methods")
    def payment_method_breakdown(self, request):
        """GET /transactions/payment-methods/ — Payment method distribution."""
        data = TransactionService.get_payment_method_breakdown(
            user=request.user,
            date_from=request.query_params.get("date_from"),
            date_to=request.query_params.get("date_to"),
        )
        return Response(data)
