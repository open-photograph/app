from collections.abc import Iterable
from tempfile import SpooledTemporaryFile
from typing import BinaryIO

from allauth.socialaccount.models import SocialAccount, SocialToken
from django.contrib.auth import get_user_model
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from shared.providers import StorageFile, StorageProvider

User = get_user_model()

# Mime type Google Drive uses internally for folders
FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"

# Fields requested from the Files.list API — keep this minimal
_FILE_FIELDS = "id, name, mimeType, size, modifiedTime"
_LIST_FIELDS = f"nextPageToken, files({_FILE_FIELDS})"


class GoogleDriveProvider(StorageProvider):
    """
    StorageProvider backed by Google Drive.

    Builds credentials from the SocialToken allauth stored after the OAuth
    connect flow (access_type=offline + prompt=consent ensures a refresh_token
    is always returned and saved by allauth).
    """

    def __init__(self, user: User) -> None:
        self._user = user
        self._service = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_credentials(self) -> Credentials:
        account = SocialAccount.objects.filter(
            user=self._user,
            provider="google",
        ).first()

        if account is None:
            raise ValueError("Google account not connected for this user.")

        token = SocialToken.objects.filter(account=account).first()

        if token is None:
            raise ValueError("No OAuth token found for the connected Google account.")

        app = account.get_provider().app

        return Credentials(
            token=token.token,
            refresh_token=token.token_secret or None,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=app.client_id,
            client_secret=app.secret,
            scopes=["https://www.googleapis.com/auth/drive.readonly"],
        )

    def _get_service(self):
        if self._service is None:
            credentials = self._get_credentials()
            self._service = build("drive", "v3", credentials=credentials)

        return self._service

    # ------------------------------------------------------------------
    # StorageProvider interface
    # ------------------------------------------------------------------

    def list_files(self, folder_id: str) -> Iterable[StorageFile]:
        """
        Yields all non-folder files directly inside `folder_id`.
        Handles Drive pagination automatically.
        """
        service = self._get_service()
        page_token = None
        query = f"'{folder_id}' in parents and mimeType != '{FOLDER_MIME_TYPE}' and trashed = false"

        while True:
            response = (
                service.files()
                .list(
                    q=query,
                    fields=_LIST_FIELDS,
                    pageSize=100,
                    pageToken=page_token,
                )
                .execute()
            )

            for item in response.get("files", []):
                yield StorageFile(
                    id=item["id"],
                    name=item["name"],
                    mime_type=item.get("mimeType", ""),
                    size=int(item["size"]) if item.get("size") else None,
                )

            page_token = response.get("nextPageToken")
            if not page_token:
                break

    def list_folders(self, parent_id: str | None = "root", search: str = "") -> Iterable[StorageFile]:
        """
        Yields all folders directly inside `parent_id` (defaults to Drive root).
        """
        service = self._get_service()
        page_token = None
        query = f"mimeType = '{FOLDER_MIME_TYPE}' and trashed = false"

        if parent_id is not None:
            escaped_parent = parent_id.replace("\\", "\\\\").replace("'", "\\'")
            query += f" and '{escaped_parent}' in parents"

        if search:
            escaped_search = search.replace("\\", "\\\\").replace("'", "\\'")
            query += f" and name contains '{escaped_search}'"

        while True:
            response = (
                service.files()
                .list(
                    q=query,
                    fields=_LIST_FIELDS,
                    pageSize=100,
                    pageToken=page_token,
                )
                .execute()
            )

            for item in response.get("files", []):
                yield StorageFile(
                    id=item["id"],
                    name=item["name"],
                    mime_type=item.get("mimeType", ""),
                    size=None,  # folders have no size
                )

            page_token = response.get("nextPageToken")
            if not page_token:
                break

    def list_folder_tree(self) -> list[StorageFile]:
        service = self._get_service()
        folders = {}
        page_token = None
        while True:
            response = (
                service.files()
                .list(
                    q=f"mimeType = '{FOLDER_MIME_TYPE}' and trashed = false",
                    fields="nextPageToken, files(id, name, mimeType, parents)",
                    pageSize=1000,
                    pageToken=page_token,
                )
                .execute()
            )
            folders.update({folder["id"]: folder for folder in response.get("files", [])})

            page_token = response.get("nextPageToken")
            if not page_token:
                break

        def folder_path(folder_id):
            parts = []
            visited = set()

            while folder_id in folders and folder_id not in visited:
                visited.add(folder_id)
                folder = folders[folder_id]
                parts.append(folder["name"])
                folder_id = next(iter(folder.get("parents", [])), None)

            return " / ".join(reversed(parts))

        return sorted(
            [
                StorageFile(
                    id=folder_id,
                    name=folder["name"],
                    mime_type=FOLDER_MIME_TYPE,
                    path=folder_path(folder_id),
                )
                for folder_id, folder in folders.items()
            ],
            key=lambda folder: (folder.path.casefold(), folder.id),
        )

    def get_file(self, file_id: str) -> StorageFile:
        service = self._get_service()
        item = service.files().get(fileId=file_id, fields=_FILE_FIELDS).execute()

        return StorageFile(
            id=item["id"],
            name=item["name"],
            mime_type=item.get("mimeType", ""),
            size=int(item["size"]) if item.get("size") else None,
        )

    def open_file(self, file_id: str) -> BinaryIO:
        """Download original bytes into a spool; caller owns and closes the returned file."""
        service = self._get_service()
        request = service.files().get_media(fileId=file_id)
        buffer = SpooledTemporaryFile(max_size=8 * 1024 * 1024, mode="w+b")  # noqa: SIM115 -- ownership transfers to caller
        downloader = MediaIoBaseDownload(buffer, request)

        try:
            done = False
            while not done:
                _, done = downloader.next_chunk()
        except Exception:
            buffer.close()
            raise

        buffer.seek(0)
        return buffer
