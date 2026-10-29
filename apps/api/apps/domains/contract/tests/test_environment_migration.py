from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class EnvironmentMigrationTests(TransactionTestCase):
    def test_existing_documents_keep_original_environments(self):
        before = [("contract", "0002_remove_signatureprovider_encrypted_token")]
        after = [("contract", "0003_remove_signatureprovider_environment_and_more")]
        executor = MigrationExecutor(connection)
        executor.migrate(before)
        try:
            apps = executor.loader.project_state(before).apps
            Client = apps.get_model("client", "Client")
            Provider = apps.get_model("contract", "SignatureProvider")
            Contract = apps.get_model("contract", "Contract")
            customer = Client.objects.create(name="Ana", email="migration@example.com")
            documents = []
            for environment in ("sandbox", "production"):
                provider = Provider.objects.create(name="ZapSign", provider="zapsign", environment=environment)
                document = Contract.objects.create(
                    title="Contrato",
                    client=customer,
                    signature_provider=provider,
                    content="Texto",
                    signer_name="Ana",
                    signer_email=customer.email,
                    status="pending",
                )
                documents.append((document.pk, environment))
            executor = MigrationExecutor(connection)
            executor.migrate(after)
            Contract = executor.loader.project_state(after).apps.get_model("contract", "Contract")
            for document_id, environment in documents:
                self.assertEqual(Contract.objects.get(pk=document_id).provider_environment, environment)
        finally:
            executor = MigrationExecutor(connection)
            executor.migrate(executor.loader.graph.leaf_nodes())
