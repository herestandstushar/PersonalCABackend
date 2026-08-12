"""
Dashboard views.
"""

from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from dashboard.services import DashboardService


class DashboardView(APIView):
    """
    GET /dashboard/ — Full dashboard data (cached).

    Returns all widget data in one response for the home dashboard.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        data = DashboardService.get_full_dashboard(request.user)
        return Response(data)


class DashboardWidgetView(APIView):
    """
    GET /dashboard/widget/<name>/ — Single widget data (for lazy loading).
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, widget_name):
        data = DashboardService.get_widget_data(request.user, widget_name)
        return Response(data)
