"""
Accounts URL configuration.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from accounts.views import AccountViewSet

router = DefaultRouter()
router.register("", AccountViewSet, basename="account")

urlpatterns = [
    path("", include(router.urls)),
]
