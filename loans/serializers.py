from rest_framework import serializers
from loans.models import Loan, EMIPayment

class EMIPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = EMIPayment
        fields = '__all__'

class LoanSerializer(serializers.ModelSerializer):
    progress_percentage = serializers.SerializerMethodField()
    
    class Meta:
        model = Loan
        fields = [
            "id", "name", "loan_type", "principal_amount", "interest_rate",
            "tenure_months", "emi_amount", "outstanding_balance",
            "start_date", "status", "linked_account", "progress_percentage",
            "created_at"
        ]
        read_only_fields = ["id", "emi_amount", "created_at"]

    def get_progress_percentage(self, obj):
        if obj.principal_amount > 0:
            paid = obj.principal_amount - obj.outstanding_balance
            return min(100, float((paid / obj.principal_amount) * 100))
        return 0

class LoanCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Loan
        fields = [
            "id", "name", "loan_type", "principal_amount", "interest_rate",
            "tenure_months", "start_date", "linked_account"
        ]
        read_only_fields = ["id"]
