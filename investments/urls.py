from django.urls import path, include
from rest_framework.routers import DefaultRouter
from investments.views import InvestmentPortfolioViewSet, InvestmentAssetViewSet

router = DefaultRouter()
router.register("portfolios", InvestmentPortfolioViewSet, basename="portfolio")
router.register("assets", InvestmentAssetViewSet, basename="asset")

urlpatterns = [
    path("", include(router.urls)),
]
