from django.urls import path, include
from rest_framework.routers import DefaultRouter
from statements.views import StatementViewSet

router = DefaultRouter()
router.register("", StatementViewSet, basename="statement")

urlpatterns = [
    path("", include(router.urls)),
]
