from typing import BinaryIO

from django.contrib.auth import get_user_model

from shared.providers import StorageFile

from ..providers import GoogleDriveProvider

User = get_user_model()


class GoogleDriveService:
    """
    Application-layer service for Google Drive operations.

    Wraps GoogleDriveProvider to provide a stable interface to the rest of
    the application. Views and tasks should depend on this service, not on
    the provider directly.
    """

    def __init__(self, user: User) -> None:
        self._provider = GoogleDriveProvider(user)

    def list_folders(self, parent_id: str | None = "root", search: str = "") -> list[StorageFile]:
        """Returns all folders inside `parent_id` (defaults to Drive root)."""
        return list(self._provider.list_folders(parent_id, search=search))

    def list_folder_tree(self) -> list[StorageFile]:
        return self._provider.list_folder_tree()

    def list_files(self, folder_id: str) -> list[StorageFile]:
        """Returns all non-folder files directly inside `folder_id`."""
        return list(self._provider.list_files(folder_id))

    def get_file(self, file_id: str) -> StorageFile:
        """Returns metadata for a single file."""
        return self._provider.get_file(file_id)

    def open_file(self, file_id: str) -> BinaryIO:
        """Downloads a file and returns its content as a binary stream."""
        return self._provider.open_file(file_id)
