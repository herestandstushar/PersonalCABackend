from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

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
        # Reload after sync parse so the client gets final status immediately.
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

        # Parse in-process (not a daemon thread). Gunicorn/Render workers can
        # recycle between requests and silently kill background import threads,
        # which left ICICI PDFs failing on the old empty-table path.
        StatementParserService.parse_and_import(
            statement.id, password, save_password
        )
