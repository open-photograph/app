from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("gallery", "0005_gallery_default_photo_price"),
    ]

    operations = [
        migrations.AddField(
            model_name="photo",
            name="is_active",
            field=models.BooleanField(
                default=True,
                help_text="Controla se a foto aparece e pode receber interacoes na galeria publica.",
            ),
        ),
    ]
