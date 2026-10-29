from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import SimpleTestCase, TestCase, TransactionTestCase, override_settings

from ..models import Setup


@override_settings(GOOGLE_CLIENT_ID="environment-client", GOOGLE_CLIENT_SECRET="environment-secret")
class SetupSelectionTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        self.user = get_user_model().objects.create_user(username="setup-admin", is_staff=True)
        self.client.force_login(self.user)

    def test_select_updates_existing_type(self):
        first = self.client.post("/api/setup/", {"type": "storage", "provider": "local"})
        second = self.client.post("/api/setup/", {"type": "storage", "provider": "google_drive"})
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()["id"], second.json()["id"])
        self.assertEqual(Setup.objects.get().provider, "google_drive")

    @override_settings(PAYMENT_VARIANTS={})
    def test_selection_is_saved_independently_of_credentials(self):
        response = self.client.post("/api/setup/", {"type": "payment", "provider": "stripe"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Setup.objects.get().provider, "stripe")
        self.assertNotIn("credentials_configured", response.json())
        self.assertNotIn("missing_settings", response.json())

    def test_each_type_has_its_own_selection(self):
        for category, provider in [("storage", "google_drive"), ("payment", "stripe")]:
            self.client.post("/api/setup/", {"type": category, "provider": provider})
        self.assertEqual(Setup.objects.count(), 2)
        response = self.client.get("/api/setup/status/")
        self.assertTrue(response.json()["has_drive"])
        self.assertTrue(response.json()["has_payment"])

    def test_secret_values_cannot_be_submitted(self):
        response = self.client.post(
            "/api/setup/",
            {
                "type": "payment",
                "provider": "stripe",
                "credentials": {"secret_key": "do-not-save"},
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Setup.objects.exists())

    def test_inactive_payment_does_not_enable_checkout(self):
        self.client.post(
            "/api/setup/",
            {"type": "payment", "provider": "stripe", "is_active": False},
            content_type="application/json",
        )
        self.assertFalse(self.client.get("/api/setup/status/").json()["has_payment"])

    def test_google_app_cleanup_preserves_oauth_tokens(self):
        import importlib
        from types import SimpleNamespace

        from allauth.socialaccount.models import SocialAccount, SocialApp, SocialToken
        from django.apps import apps

        app = SocialApp.objects.create(provider="google", name="Legacy", client_id="old-client", secret="old-secret")
        account = SocialAccount.objects.create(user=self.user, provider="google", uid="existing-account")
        token = SocialToken.objects.create(account=account, app=app, token="access-token", token_secret="refresh-token")
        migration = importlib.import_module("apps.domains.setup.migrations.0005_environment_google_app")
        with override_settings(GOOGLE_CLIENT_ID="", GOOGLE_CLIENT_SECRET=""):
            with self.assertRaisesRegex(RuntimeError, "Configure"):
                migration.remove_database_google_apps(apps, SimpleNamespace(connection=connection))
            self.assertTrue(SocialApp.objects.filter(pk=app.pk).exists())
        migration.remove_database_google_apps(apps, SimpleNamespace(connection=connection))
        token.refresh_from_db()
        self.assertIsNone(token.app_id)
        self.assertEqual(token.token_secret, "refresh-token")
        self.assertTrue(SocialAccount.objects.filter(pk=account.pk).exists())
        self.assertFalse(SocialApp.objects.filter(provider="google").exists())


class SetupMigrationTests(TransactionTestCase):
    def test_consolidation_preserves_latest_active_setup_per_type(self):
        executor = MigrationExecutor(connection)
        previous = [("setup", "0001_initial")]
        current = [("setup", "0002_unique_setup_type")]
        executor.migrate(previous)
        historical_setup = executor.loader.project_state(previous).apps.get_model("setup", "Setup")
        try:
            historical_setup.objects.create(name="Old", type="storage", provider="local")
            retained = historical_setup.objects.create(name="Active", type="storage", provider="google_drive")
            historical_setup.objects.create(name="Inactive", type="storage", provider="s3", is_active=False)
            payment = historical_setup.objects.create(name="Stripe", type="payment", provider="stripe")
            executor = MigrationExecutor(connection)
            executor.migrate(current)
            self.assertSetEqual(set(Setup.objects.values_list("pk", flat=True)), {retained.pk, payment.pk})
        finally:
            MigrationExecutor(connection).migrate([("setup", "0005_environment_google_app")])


class EnvironmentConfigurationTests(SimpleTestCase):
    def load_settings(self, values):
        import os
        import runpy
        from pathlib import Path
        from unittest.mock import patch

        path = Path(__file__).resolve().parents[3] / "config" / "settings.py"
        with patch.dict(os.environ, values), patch("environ.Env.read_env"):
            return runpy.run_path(str(path))

    def test_payment_keys_and_google_app_are_loaded_from_environment(self):
        configured = self.load_settings(
            {
                "PAYMENT_PROVIDER": "stripe",
                "STRIPE_SECRET_KEY": "environment-stripe",
                "MERCADO_PAGO_ACCESS_TOKEN": "environment-mercado",
                "MERCADO_PAGO_SANDBOX": "True",
                "GOOGLE_CLIENT_ID": "environment-google",
                "GOOGLE_CLIENT_SECRET": "google-secret",
                "SYSTEM_STORAGE_PROVIDER": "local",
            }
        )
        self.assertEqual(configured["PAYMENT_VARIANTS"]["stripe"][1]["api_key"], "environment-stripe")
        self.assertEqual(configured["PAYMENT_VARIANTS"]["mercado_pago"][1]["access_token"], "environment-mercado")
        self.assertTrue(configured["PAYMENT_VARIANTS"]["mercado_pago"][1]["sandbox"])
        self.assertEqual(configured["SOCIALACCOUNT_PROVIDERS"]["google"]["APP"]["secret"], "google-secret")
        self.assertNotIn("PAYMENT_VARIANT_FACTORY", configured)

    def test_storage_selection_is_independent_of_debug(self):
        configured = self.load_settings(
            {
                "SYSTEM_STORAGE_PROVIDER": "s3",
                "DJANGO_DEBUG": "True",
                "AWS_ACCESS_KEY_ID": "test-access",
                "AWS_SECRET_ACCESS_KEY": "test-secret",
                "AWS_STORAGE_BUCKET_NAME": "test-bucket",
                "PAYMENT_PROVIDER": "",
            }
        )
        self.assertEqual(configured["STORAGES"]["default"]["BACKEND"], "storages.backends.s3.S3Storage")
        self.assertEqual(configured["SYSTEM_STORAGE_PROVIDER"], "s3")
        configured = self.load_settings(
            {"SYSTEM_STORAGE_PROVIDER": "local", "DJANGO_DEBUG": "False", "PAYMENT_PROVIDER": ""}
        )
        self.assertEqual(configured["STORAGES"]["default"]["BACKEND"], "django.core.files.storage.FileSystemStorage")
        self.assertEqual(configured["SYSTEM_STORAGE_PROVIDER"], "local")

    def test_unconfigured_provider_is_not_registered(self):
        configured = self.load_settings({"STRIPE_SECRET_KEY": ""})
        self.assertNotIn("stripe", configured["PAYMENT_VARIANTS"])
