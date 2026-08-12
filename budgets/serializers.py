from rest_framework import serializers
from budgets.models import Budget
from categories.serializers import CategorySerializer

class BudgetSerializer(serializers.ModelSerializer):
    category_detail = CategorySerializer(source="category", read_only=True)
    
    class Meta:
        model = Budget
        fields = [
            "id", "category", "category_detail", "amount", 
            "period", "is_rollover", "is_active", 
            "start_date", "end_date", "created_at"
        ]
        read_only_fields = ["id", "created_at"]

class BudgetCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Budget
        fields = [
            "id", "category", "amount", "period",
            "is_rollover", "start_date", "end_date",
        ]
        read_only_fields = ["id"]
