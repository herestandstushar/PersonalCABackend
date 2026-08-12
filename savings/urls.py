from django.urls import path, include
from rest_framework.routers import DefaultRouter
from savings.views import SavingsGoalViewSet

router = DefaultRouter()
router.register("", SavingsGoalViewSet, basename="savings-goal")

urlpatterns = [
    path("", include(router.urls)),
]
