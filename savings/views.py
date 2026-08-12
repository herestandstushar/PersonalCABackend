from decimal import Decimal, InvalidOperation

from rest_framework import permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from core.permissions import IsOwner
from savings.models import SavingsGoal
from savings.serializers import SavingsGoalSerializer, SavingsGoalCreateSerializer, GoalContributionSerializer
from savings.services import SavingsService

class SavingsGoalViewSet(ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsOwner]
    
    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return SavingsGoalCreateSerializer
        return SavingsGoalSerializer

    def get_queryset(self):
        return SavingsGoal.objects.filter(user=self.request.user).prefetch_related("contributions")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=["post"])
    def contribute(self, request, pk=None):
        """Add money to a savings goal"""
        amount = request.data.get("amount")
        notes = request.data.get("notes", "")

        # Decimal, not float: the goal's balance is a Decimal column and mixing
        # the two raises a TypeError on the running total.
        try:
            amount = Decimal(str(amount))
        except (TypeError, ValueError, InvalidOperation):
            return Response(
                {"errors": [{"code": "invalid", "message": "Invalid amount.", "field": "amount"}]},
                status=status.HTTP_400_BAD_REQUEST,
            )


        contribution = SavingsService.add_contribution(
            user=request.user,
            goal_id=pk,
            amount=amount,
            notes=notes
        )
        
        return Response(GoalContributionSerializer(contribution).data, status=status.HTTP_201_CREATED)
