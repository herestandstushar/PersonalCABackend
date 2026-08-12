from rest_framework import permissions
from rest_framework.viewsets import ModelViewSet
from rest_framework.decorators import action
from rest_framework.response import Response

from core.permissions import IsOwner
from investments.models import InvestmentPortfolio, InvestmentAsset
from investments.serializers import InvestmentPortfolioSerializer, InvestmentAssetSerializer

class InvestmentPortfolioViewSet(ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsOwner]
    serializer_class = InvestmentPortfolioSerializer

    def get_queryset(self):
        return InvestmentPortfolio.objects.filter(user=self.request.user).prefetch_related("assets")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class InvestmentAssetViewSet(ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = InvestmentAssetSerializer

    def get_queryset(self):
        return InvestmentAsset.objects.filter(portfolio__user=self.request.user)
