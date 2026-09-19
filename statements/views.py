from rest_framework import permissions, status
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

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        # Return immediately while import continues in a background thread.
        statement = Statement.objects.select_related("account").get(
            pk=serializer.instance.pk
        )
        return Response(
            StatementSerializer(statement).data,
            status=status.HTTP_201_CREATED,
        )

    def perform_create(self, serializer):
        # Password unlocks encrypted PDFs and is never persisted on Statement.
        password = serializer.validated_data.pop("password", "") or ""
        save_password = serializer.validated_data.pop("save_password", True)
        file = self.request.data.get("file")
        statement = serializer.save(user=self.request.user, filename=file.name)

        # Background import — sync parse of ~80 ICICI rows was taking minutes
        # (Neon round-trip per txn) and the browser axios 30s timeout canceled it.
        thread = threading.Thread(
            target=StatementParserService.parse_and_import,
            args=(statement.id, password, save_password),
            daemon=True,
        )
        thread.start()
