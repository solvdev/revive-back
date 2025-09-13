# Generated manually for performance optimization

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_initial'),
    ]

    operations = [
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_client_status ON accounts_client (status);",
            reverse_sql="DROP INDEX IF EXISTS idx_client_status;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_client_name ON accounts_client (first_name, last_name);",
            reverse_sql="DROP INDEX IF EXISTS idx_client_name;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_client_status_name ON accounts_client (status, first_name, last_name);",
            reverse_sql="DROP INDEX IF EXISTS idx_client_status_name;"
        ),
    ]
