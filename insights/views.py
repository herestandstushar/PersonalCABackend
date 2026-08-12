from rest_framework import permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response

from insights.services import InsightsService

class InsightsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        insights = InsightsService.generate_insights(request.user)
        return Response({"insights": insights}, status=status.HTTP_200_OK)
