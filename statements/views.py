from rest_framework import permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
import threading

from core.permissions import IsOwner
from statements.models import Statement
from statements.serializers import StatementSerializer, StatementCreateSerializer
from statements.services import StatementParserService

class StatementViewSet(ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsOwner]
    
    def get_serializer_class(self):
        if self.action == "create":
            return StatementCreateSerializer
        return StatementSerializer

    def get_queryset(self):
        return Statement.objects.filter(user=self.request.user).select_related("account")

    def perform_create(self, serializer):
        # Password unlocks encrypted PDFs and is never persisted.
        password = serializer.validated_data.pop("password", "") or ""
        file = self.request.data.get("file")
        statement = serializer.save(user=self.request.user, filename=file.name)

        # MVP: parse in a background thread (Celery in production).
        thread = threading.Thread(
            target=StatementParserService.parse_and_import,
            args=(statement.id, password),
        )
        thread.daemon = True
        thread.start()
