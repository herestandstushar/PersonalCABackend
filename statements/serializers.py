from rest_framework import serializers
from statements.models import Statement, StatementMappingRule
from accounts.serializers import AccountSerializer

class StatementMappingRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = StatementMappingRule
        fields = '__all__'

class StatementSerializer(serializers.ModelSerializer):
    account_detail = AccountSerializer(source="account", read_only=True)
    
    class Meta:
        model = Statement
        fields = [
            "id", "account", "account_detail", "file", "filename",
            "status", "error_message", "transactions_imported",
            "month", "year", "created_at"
        ]
        read_only_fields = ["id", "status", "error_message", "transactions_imported", "created_at", "filename"]

class StatementCreateSerializer(serializers.ModelSerializer):
    # Write-only: used to unlock password-protected PDFs, never stored.
    password = serializers.CharField(
        required=False,
        allow_blank=True,
        write_only=True,
        help_text="Password for encrypted PDF statements.",
    )

    class Meta:
        model = Statement
        fields = [
            "id", "account", "file", "month", "year", "password",
            "status", "filename", "transactions_imported", "error_message",
        ]
        read_only_fields = [
            "id", "status", "filename", "transactions_imported", "error_message",
        ]
