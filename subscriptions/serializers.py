from rest_framework import serializers
from subscriptions.models import Subscription, RecurringTransaction

class SubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = [
            "id", "name", "amount", "billing_cycle", 
            "next_billing_date", "category", "account", 
            "status", "auto_renew", "url", "color", "icon", "created_at"
        ]
        read_only_fields = ["id", "created_at"]

class RecurringTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecurringTransaction
        fields = '__all__'
        read_only_fields = ["id", "last_processed_date", "created_at"]
