from django.db import migrations, models


def preserve_document_environments(apps, schema_editor):
    Contract = apps.get_model("contract", "Contract")
    Provider = apps.get_model("contract", "SignatureProvider")
    database = schema_editor.connection.alias
    for provider in Provider.objects.using(database).all():
        Contract.objects.using(database).filter(signature_provider_id=provider.pk).update(
            provider_environment=provider.environment,
        )


class Migration(migrations.Migration):
    dependencies = [("contract", "0002_remove_signatureprovider_encrypted_token")]
    operations = [
        migrations.AddField(
            model_name="contract", name="provider_environment",
            field=models.CharField(blank=True, default="", max_length=20),
        ),
        migrations.RunPython(preserve_document_environments, migrations.RunPython.noop),
        migrations.RemoveField(model_name="signatureprovider", name="environment"),
    ]
