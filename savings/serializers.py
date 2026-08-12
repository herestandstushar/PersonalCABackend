from rest_framework import serializers
from savings.models import SavingsGoal, GoalContribution

class GoalContributionSerializer(serializers.ModelSerializer):
    class Meta:
        model = GoalContribution
        fields = ["id", "amount", "date", "notes", "created_at"]
        read_only_fields = ["id", "date", "created_at"]

class SavingsGoalSerializer(serializers.ModelSerializer):
    progress_percentage = serializers.FloatField(read_only=True)
    contributions = GoalContributionSerializer(many=True, read_only=True)
    
    class Meta:
        model = SavingsGoal
        fields = [
            "id", "name", "target_amount", "current_amount", 
            "target_date", "status", "icon", "color", 
            "notes", "linked_account", "progress_percentage",
            "contributions", "created_at"
        ]
        read_only_fields = ["id", "current_amount", "status", "created_at"]

class SavingsGoalCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavingsGoal
        fields = [
            "id", "name", "target_amount", "current_amount",
            "target_date", "icon", "color", "notes", "linked_account"
        ]
        read_only_fields = ["id"]
