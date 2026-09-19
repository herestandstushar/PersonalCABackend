from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("statements", "0003_statement_account_optional"),
    ]

    operations = [
        migrations.AddField(
            model_name="statement",
            name="transactions_skipped",
            field=models.IntegerField(
                default=0,
                help_text="Rows skipped as duplicates of existing account transactions.",
            ),
        ),
    ]
