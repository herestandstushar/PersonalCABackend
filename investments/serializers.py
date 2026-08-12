from rest_framework import serializers
from investments.models import InvestmentPortfolio, InvestmentAsset

class InvestmentAssetSerializer(serializers.ModelSerializer):
    total_invested = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    current_value = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    return_percentage = serializers.FloatField(read_only=True)

    class Meta:
        model = InvestmentAsset
        fields = '__all__'

class InvestmentPortfolioSerializer(serializers.ModelSerializer):
    assets = InvestmentAssetSerializer(many=True, read_only=True)
    total_invested = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    current_value = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    total_returns = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)

    class Meta:
        model = InvestmentPortfolio
        fields = [
            "id", "name", "assets", "total_invested", 
            "current_value", "total_returns", "created_at"
        ]
        read_only_fields = ["id", "created_at"]
