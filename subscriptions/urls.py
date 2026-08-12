from django.urls import path, include
from rest_framework.routers import DefaultRouter
from subscriptions.views import SubscriptionViewSet, RecurringTransactionViewSet

router = DefaultRouter()
router.register("subscriptions", SubscriptionViewSet, basename="subscription")
router.register("recurring", RecurringTransactionViewSet, basename="recurring")

urlpatterns = [
    path("", include(router.urls)),
]
