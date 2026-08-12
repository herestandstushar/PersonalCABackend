from rest_framework import permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from core.permissions import IsOwner
from budgets.models import Budget
from budgets.serializers import BudgetSerializer, BudgetCreateSerializer
from budgets.services import BudgetService

class BudgetViewSet(ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsOwner]
    
    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return BudgetCreateSerializer
        return BudgetSerializer

    def get_queryset(self):
        return Budget.objects.filter(user=self.request.user).select_related("category")

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        budget = BudgetService.create_budget(request.user, serializer.validated_data)
        return Response(BudgetSerializer(budget).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"])
    def status(self, request):
        """Get calculated status of all budgets against actual spending"""
        data = BudgetService.get_budget_status(request.user)
        return Response(data)
