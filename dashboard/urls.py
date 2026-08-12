from django.urls import path

from dashboard.views import DashboardView, DashboardWidgetView

urlpatterns = [
    path("", DashboardView.as_view(), name="dashboard"),
    path("widget/<str:widget_name>/", DashboardWidgetView.as_view(), name="dashboard-widget"),
]
