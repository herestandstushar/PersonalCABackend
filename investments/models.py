"""
Investment models.
"""
from django.conf import settings
from django.db import models

from core.models import BaseModel


class AssetType(models.TextChoices):
    STOCK = "stock", "Stock/Equity"
    CRYPTO = "crypto", "Cryptocurrency"
    MUTUAL_FUND = "mutual_fund", "Mutual Fund"
    FIXED_DEPOSIT = "fixed_deposit", "Fixed Deposit"
    REAL_ESTATE = "real_estate", "Real Estate"
    OTHER = "other", "Other"


class InvestmentPortfolio(BaseModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="portfolios",
    )
    name = models.CharField(max_length=100, default="My Portfolio")

    class Meta:
        db_table = "investment_portfolios"

    def __str__(self):
        return f"{self.user.email} - {self.name}"

    @property
    def total_invested(self):
        return sum(asset.total_invested for asset in self.assets.all())

    @property
    def current_value(self):
        return sum(asset.current_value for asset in self.assets.all())

    @property
    def total_returns(self):
        return self.current_value - self.total_invested


class InvestmentAsset(BaseModel):
    portfolio = models.ForeignKey(
        InvestmentPortfolio, 
        on_delete=models.CASCADE, 
        related_name="assets"
    )
    name = models.CharField(max_length=255)
    symbol = models.CharField(max_length=20, blank=True)
    asset_type = models.CharField(
        max_length=20, 
        choices=AssetType.choices, 
        default=AssetType.OTHER
    )
    
    quantity = models.DecimalField(max_digits=15, decimal_places=6)
    average_buy_price = models.DecimalField(max_digits=15, decimal_places=2)
    current_price = models.DecimalField(max_digits=15, decimal_places=2)
    
    class Meta:
        db_table = "investment_assets"

    def __str__(self):
        return f"{self.name} ({self.symbol})"

    @property
    def total_invested(self):
        return self.quantity * self.average_buy_price

    @property
    def current_value(self):
        return self.quantity * self.current_price

    @property
    def return_percentage(self):
        if self.total_invested > 0:
            return ((self.current_value - self.total_invested) / self.total_invested) * 100
        return 0
