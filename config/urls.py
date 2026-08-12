"""
URL Configuration for FinSight API.

All API endpoints are versioned under /api/v1/.
Swagger and ReDoc documentation available at /api/docs/ and /api/redoc/.
"""

from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

api_v1_patterns = [
    path("auth/", include("authentication.urls")),
    path("users/", include("users.urls")),
    path("accounts/", include("accounts.urls")),
    path("categories/", include("categories.urls")),
    path("transactions/", include("transactions.urls")),
    path("statements/", include("statements.urls")),
    path("budgets/", include("budgets.urls")),
    path("subscriptions/", include("subscriptions.urls")),
    path("loans/", include("loans.urls")),
    path("investments/", include("investments.urls")),
    path("savings/", include("savings.urls")),
    path("analytics/", include("analytics.urls")),
    path("insights/", include("insights.urls")),
    path("notifications/", include("notifications.urls")),
    path("reports/", include("reports.urls")),
    path("dashboard/", include("dashboard.urls")),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    # API v1
    path("api/v1/", include(api_v1_patterns)),
    # API Documentation
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "api/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
]
