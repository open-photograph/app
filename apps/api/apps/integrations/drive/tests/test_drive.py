from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

from allauth.socialaccount.models import SocialAccount
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from shared.providers import StorageFile

from ..providers.google_drive import GoogleDriveProvider


@override_settings(
    GOOGLE_CLIENT_ID="test-client",
    GOOGLE_CLIENT_SECRET="test-secret",
    SOCIALACCOUNT_PROVIDERS={
        "google": {
            "APP": {"client_id": "test-client", "secret": "test-secret", "key": ""},
            "AUTH_PARAMS": {"access_type": "offline", "prompt": "consent"},
            "SCOPE": ["profile", "email", "https://www.googleapis.com/auth/drive.readonly"],
        }
    },
    SESSION_ENGINE="django.contrib.sessions.backends.db",
    ALLOWED_HOSTS=["testserver"],
    CSRF_TRUSTED_ORIGINS=["http://localhost:5173"],
    SECURE_SSL_REDIRECT=False,
)
class GoogleDriveConnectTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="drive-admin", is_staff=True)
        self.client.force_login(self.user)

    def test_connect_returns_google_url_and_stores_headless_state(self):
        callback = "http://localhost:5173/admin/settings/drive"
        response = self.client.post(
            "/api/drive/google/connect/", {"callback_url": callback}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        authorization = urlparse(response.json()["url"])
        self.assertEqual(authorization.hostname, "accounts.google.com")
        query = parse_qs(authorization.query)
        self.assertEqual(query["redirect_uri"], ["http://testserver/api/allauth/google/login/callback/"])
        self.assertEqual(query["access_type"], ["offline"])
        self.assertIn("https://www.googleapis.com/auth/drive.readonly", query["scope"][0])
        state = self.client.session["socialaccount_states"][query["state"][0]][0]
        self.assertEqual(state["process"], "connect")
        self.assertTrue(state["headless"])
        self.assertEqual(state["next"], callback)

    @override_settings(GOOGLE_CLIENT_ID="", GOOGLE_CLIENT_SECRET="", SOCIALACCOUNT_PROVIDERS={"google": {}})
    def test_missing_credentials_return_validation_error(self):
        response = self.client.post(
            "/api/drive/google/connect/",
            {"callback_url": "http://testserver/setup/drive"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_untrusted_return_url_is_rejected(self):
        response = self.client.post(
            "/api/drive/google/connect/",
            {"callback_url": "https://untrusted.example/"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_status_returns_actual_google_callback(self):
        response = self.client.get("/api/drive/google/status/")
        self.assertEqual(response.json()["callback_url"], "http://testserver/api/allauth/google/login/callback/")

    def test_folder_search_returns_names_and_ids(self):
        SocialAccount.objects.create(user=self.user, provider="google", uid="folder-test")
        with patch("apps.integrations.drive.views.google_drive.GoogleDriveService") as service:
            service.return_value.list_folders.return_value = [
                StorageFile(id="folder-1", name="Ensaio", mime_type="application/vnd.google-apps.folder")
            ]
            response = self.client.get("/api/drive/google/folders/", {"search": "Ensaio"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()[0]["name"], "Ensaio")
            service.return_value.list_folders.assert_called_once_with(None, search="Ensaio")

    def test_folder_search_escapes_google_query(self):
        provider = GoogleDriveProvider(self.user)
        provider._service = MagicMock()
        provider._service.files.return_value.list.return_value.execute.return_value = {"files": []}
        list(provider.list_folders(None, search="Ana's"))
        query = provider._service.files.return_value.list.call_args.kwargs["q"]
        self.assertIn("name contains 'Ana\\'s'", query)
        self.assertNotIn("in parents", query)

    def test_folder_tree_builds_nested_paths_across_pages(self):
        provider = GoogleDriveProvider(self.user)
        provider._service = MagicMock()
        provider._service.files.return_value.list.return_value.execute.side_effect = [
            {"files": [{"id": "edited", "name": "editada", "parents": ["date"]}], "nextPageToken": "page-2"},
            {
                "files": [
                    {"id": "photo", "name": "fotografia", "parents": ["root"]},
                    {"id": "date", "name": "10-12-2026", "parents": ["photo"]},
                ]
            },
        ]
        folders = provider.list_folder_tree()
        paths = {folder.id: folder.path for folder in folders}
        self.assertEqual(paths["edited"], "fotografia / 10-12-2026 / editada")
        self.assertEqual(paths["date"], "fotografia / 10-12-2026")
        self.assertEqual(provider._service.files.return_value.list.call_count, 2)

    def test_folder_tree_endpoint_returns_paths(self):
        SocialAccount.objects.create(user=self.user, provider="google", uid="tree-test")
        with patch("apps.integrations.drive.views.google_drive.GoogleDriveService") as service:
            service.return_value.list_folder_tree.return_value = [
                StorageFile(
                    id="edited",
                    name="editada",
                    mime_type="application/vnd.google-apps.folder",
                    path="fotografia / 10-12-2026 / editada",
                )
            ]
            response = self.client.get("/api/drive/google/folders/", {"tree": "true"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()[0]["path"], "fotografia / 10-12-2026 / editada")


class MediaStorageIsolationTests(TestCase):
    def test_original_source_selection_does_not_change_internal_media_storage(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory

        from django.core.files.base import ContentFile
        from django.core.files.storage import default_storage

        from apps.domains.setup.models import Setup

        with (
            TemporaryDirectory() as system_root,
            override_settings(
                STORAGES={
                    "default": {
                        "BACKEND": "django.core.files.storage.FileSystemStorage",
                        "OPTIONS": {"location": system_root},
                    },
                }
            ),
        ):
            choice = Setup.objects.create(name="Originals", type="storage", provider="local")
            for source in ("local", "s3", "google_drive"):
                choice.provider = source
                choice.save()
                name = f"{source}-watermark.webp"
                default_storage.save(name, ContentFile(b"system-media"))
                self.assertEqual((Path(system_root) / name).read_bytes(), b"system-media")
