from rest_framework import permissions
from rest_framework.viewsets import ModelViewSet

from core.permissions import IsOwner
from subscriptions.models import Subscription, RecurringTransaction
from subscriptions.serializers import SubscriptionSerializer, RecurringTransactionSerializer

class SubscriptionViewSet(ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsOwner]
    serializer_class = SubscriptionSerializer

    def get_queryset(self):
        return Subscription.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class RecurringTransactionViewSet(ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsOwner]
    serializer_class = RecurringTransactionSerializer

    def get_queryset(self):
        return RecurringTransaction.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
