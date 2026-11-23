from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("conversations", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="generationmetadata",
            name="diagnostics",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AlterField(
            model_name="generationmetadata",
            name="verification_status",
            field=models.CharField(
                choices=[
                    ("synthetic", "Synthetic mock response"),
                    ("verified", "Claims verified"),
                    ("partially_verified", "Some claims omitted by verifier"),
                    ("abstained", "Insufficient authorized evidence"),
                    ("not_reported", "Not reported by RAG API"),
                    ("failed", "Generation failed"),
                ],
                max_length=24,
            ),
        ),
    ]
