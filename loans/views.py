from rest_framework import permissions, status
from rest_framework.viewsets import ModelViewSet

from core.permissions import IsOwner
from loans.models import Loan
from loans.serializers import LoanSerializer, LoanCreateSerializer
from loans.services import LoanService

class LoanViewSet(ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsOwner]
    
    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return LoanCreateSerializer
        return LoanSerializer

    def get_queryset(self):
        return Loan.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        loan = serializer.save(
            user=self.request.user,
            outstanding_balance=serializer.validated_data['principal_amount']
        )
        LoanService.setup_loan(loan)
