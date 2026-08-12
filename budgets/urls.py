from django.urls import path, include
from rest_framework.routers import DefaultRouter
from budgets.views import BudgetViewSet

router = DefaultRouter()
router.register("", BudgetViewSet, basename="budget")

urlpatterns = [
    path("", include(router.urls)),
]
