"""
Management command to seed default data (currencies, categories).
"""

from django.core.management.base import BaseCommand

from categories.services import CategoryService
from users.models import Currency


CURRENCIES = [
    {"code": "USD", "name": "US Dollar", "symbol": "$", "exchange_rate_to_usd": 1.0},
    {"code": "EUR", "name": "Euro", "symbol": "€", "exchange_rate_to_usd": 0.92},
    {"code": "GBP", "name": "British Pound", "symbol": "£", "exchange_rate_to_usd": 0.79},
    {"code": "INR", "name": "Indian Rupee", "symbol": "₹", "exchange_rate_to_usd": 83.5},
    {"code": "JPY", "name": "Japanese Yen", "symbol": "¥", "exchange_rate_to_usd": 149.5},
    {"code": "AUD", "name": "Australian Dollar", "symbol": "A$", "exchange_rate_to_usd": 1.53},
    {"code": "CAD", "name": "Canadian Dollar", "symbol": "C$", "exchange_rate_to_usd": 1.36},
    {"code": "CHF", "name": "Swiss Franc", "symbol": "CHF", "exchange_rate_to_usd": 0.88},
    {"code": "CNY", "name": "Chinese Yuan", "symbol": "¥", "exchange_rate_to_usd": 7.24},
    {"code": "SGD", "name": "Singapore Dollar", "symbol": "S$", "exchange_rate_to_usd": 1.34},
    {"code": "AED", "name": "UAE Dirham", "symbol": "د.إ", "exchange_rate_to_usd": 3.67},
    {"code": "SAR", "name": "Saudi Riyal", "symbol": "﷼", "exchange_rate_to_usd": 3.75},
    {"code": "BRL", "name": "Brazilian Real", "symbol": "R$", "exchange_rate_to_usd": 4.97},
    {"code": "KRW", "name": "South Korean Won", "symbol": "₩", "exchange_rate_to_usd": 1320.0},
    {"code": "MXN", "name": "Mexican Peso", "symbol": "MX$", "exchange_rate_to_usd": 17.15},
    {"code": "THB", "name": "Thai Baht", "symbol": "฿", "exchange_rate_to_usd": 35.5},
    {"code": "ZAR", "name": "South African Rand", "symbol": "R", "exchange_rate_to_usd": 18.7},
    {"code": "NZD", "name": "New Zealand Dollar", "symbol": "NZ$", "exchange_rate_to_usd": 1.63},
    {"code": "SEK", "name": "Swedish Krona", "symbol": "kr", "exchange_rate_to_usd": 10.5},
    {"code": "NOK", "name": "Norwegian Krone", "symbol": "kr", "exchange_rate_to_usd": 10.8},
]


class Command(BaseCommand):
    help = "Seed default currencies and categories"

    def handle(self, *args, **options):
        # Seed currencies
        currency_count = 0
        for curr_data in CURRENCIES:
            _, created = Currency.objects.get_or_create(
                code=curr_data["code"],
                defaults=curr_data,
            )
            if created:
                currency_count += 1

        self.stdout.write(
            self.style.SUCCESS(f"Seeded {currency_count} currencies")
        )

        # Seed categories
        cat_count = CategoryService.seed_system_categories()
        self.stdout.write(
            self.style.SUCCESS(f"Seeded {cat_count} categories")
        )

        self.stdout.write(self.style.SUCCESS("Seed data complete!"))
