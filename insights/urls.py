from django.urls import path
from insights.views import InsightsView

urlpatterns = [
    path("", InsightsView.as_view(), name="insights-list"),
]
