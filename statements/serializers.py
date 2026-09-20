from rest_framework import serializers

from accounts.models import Account
from accounts.serializers import AccountSerializer
from statements.models import Statement, StatementMappingRule


class StatementMappingRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = StatementMappingRule
        fields = "__all__"


class StatementSerializer(serializers.ModelSerializer):
    account_detail = AccountSerializer(source="account", read_only=True)

    class Meta:
        model = Statement
        fields = [
            "id",
            "account",
            "account_detail",
            "file",
            "filename",
            "status",
            "error_message",
            "transactions_imported",
            "transactions_skipped",
            "month",
            "year",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "error_message",
            "transactions_imported",
            "transactions_skipped",
            "created_at",
            "filename",
        ]


class StatementCreateSerializer(serializers.ModelSerializer):
    # Write-only: used to unlock password-protected PDFs, never stored on Statement.
    password = serializers.CharField(
        required=False,
        allow_blank=True,
        write_only=True,
        help_text="Password for encrypted PDF statements.",
    )
    save_password = serializers.BooleanField(
        required=False,
        default=True,
        write_only=True,
        help_text="When true, store the PDF password on the resolved account for next time.",
    )
    account = serializers.PrimaryKeyRelatedField(
        queryset=Account.objects.none(),
        required=False,
        allow_null=True,
        help_text="Optional for smart PDF imports — auto-detected/created from the file.",
    )

    class Meta:
        model = Statement
        fields = [
            "id",
            "account",
            "file",
            "month",
            "year",
            "password",
            "save_password",
            "status",
            "filename",
            "transactions_imported",
            "transactions_skipped",
            "error_message",
        ]
        read_only_fields = [
            "id",
            "status",
            "filename",
            "transactions_imported",
            "transactions_skipped",
            "error_message",
        ]
        extra_kwargs = {
            "account": {"required": False, "allow_null": True},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Multipart "auto-detect" uploads omit account — keep it optional always.
        account_field = self.fields.get("account")
        if account_field is not None:
            account_field.required = False
            account_field.allow_null = True
        request = self.context.get("request")
        if request and getattr(request, "user", None) and account_field is not None:
            account_field.queryset = Account.objects.filter(
                user=request.user, is_active=True
            )

    def to_internal_value(self, data):
        # FormData may send account="" for the placeholder option; treat as omitted.
        if hasattr(data, "copy"):
            data = data.copy()
            raw = data.get("account")
            if raw in ("", None, "null", "undefined"):
                data.pop("account", None)
        return super().to_internal_value(data)

    def validate(self, attrs):
        upload = attrs.get("file")
        account = attrs.get("account")
        name = (getattr(upload, "name", "") or "").lower()
        content_type = (getattr(upload, "content_type", "") or "").lower()
        is_pdf = name.endswith(".pdf") or "pdf" in content_type
        if not account and not is_pdf:
            raise serializers.ValidationError(
                {
                    "account": (
                        "Select an account for CSV/Excel uploads. "
                        "PDFs can auto-detect the bank account."
                    )
                }
            )
        return attrs
