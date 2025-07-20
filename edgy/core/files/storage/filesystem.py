import contextlib
import os
from datetime import datetime, timezone
from functools import cached_property
from threading import Lock
from typing import Any, BinaryIO, cast
from urllib.parse import urljoin

from edgy.conf import settings
from edgy.core.files.base import File
from edgy.core.files.move import file_move_safe
from edgy.utils.path import filepath_to_uri, safe_join

from .base import Storage


class FileSystemStorage(Storage):
    """
    A file storage backend that stores files on the local filesystem.

    This class extends the abstract `Storage` base class, providing concrete
    implementations for file operations like opening, saving, deleting,
    checking existence, listing directories, getting file size, and generating URLs.

    It handles path construction, directory creation, file permissions, and
    provides basic multi-process safety for filename reservation.

    Attributes:
        OS_OPEN_FLAGS (int): Bitmask for file opening flags, including write-only,
                             create, exclusive creation, and binary mode (if available).
    """

    # Flags used for opening files at the OS level (e.g., via os.open).
    # os.O_WRONLY: Open for writing only.
    # os.O_CREAT: Create file if it does not exist.
    # os.O_EXCL: Exclusive creation, error if file already exists.
    # getattr(os, "O_BINARY", 0): Add O_BINARY flag on Windows to open in binary mode.
    OS_OPEN_FLAGS = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)

    def __init__(
        self,
        location: str | os.PathLike | None = None,
        base_url: str | None = None,
        file_permissions_mode: int | None = None,
        directory_permissions_mode: int | None = None,
    ) -> None:
        """
        Initializes the FileSystemStorage instance.

        Args:
            location (str | os.PathLike | None): The root directory where files will be stored.
                                                  If None, `settings.media_root` is used.
            base_url (str | None): The base URL for serving files from this storage.
                                   If None, `settings.media_url` is used.
            file_permissions_mode (int | None): The numeric mode (e.g., 0o644) for new files.
                                                If None, `settings.file_upload_permissions` is used.
            directory_permissions_mode (int | None): The numeric mode (e.g., 0o755) for new directories.
                                                     If None, `settings.file_upload_directory_permissions` is used.
        """
        self._location = location
        self._base_url = base_url
        self._file_permissions_mode = file_permissions_mode
        self._directory_permissions_mode = directory_permissions_mode
        # Lock for ensuring atomicity during name reservation in multi-threaded environments.
        self._name_lock = Lock()
        # Dictionary to keep track of reserved names and their reservation times.
        self._name_dict: dict[str, datetime] = {}

    def reserve_name(self, name: str) -> bool:
        """
        Attempts to reserve a filename for exclusive use. This helps prevent
        race conditions in multi-threaded or multi-process environments where
        multiple operations might try to save to the same filename.

        Args:
            name (str): The filename to reserve.

        Returns:
            bool: True if the name was successfully reserved (i.e., it doesn't exist
                  and isn't currently in the reservation dictionary), False otherwise.
        """
        with self._name_lock:  # Acquire lock for thread safety
            # Check if the file exists on disk or if the name is already reserved.
            # A timeout for reservation could be added here if long-lived reservations are an issue.
            if not self.exists(name) and name not in self._name_dict:
                self._name_dict[name] = datetime.now(timezone.utc)  # Record reservation time
                return True
        return False

    def unreserve_name(self, name: str) -> bool:
        """
        Releases a previously reserved filename. This should be called after a
        file operation (like `save`) is completed or aborted, to make the name
        available for others.

        Args:
            name (str): The filename to unreserve.

        Returns:
            bool: True if the name was successfully unreserved, False if the
                  name was not found in the reserved list (e.g., never reserved
                  or already unreserved).
        """
        try:
            with self._name_lock:  # Acquire lock for thread safety
                del self._name_dict[name]  # Remove the name from the reserved list
                return True
        except KeyError:
            # If the name was not in the dictionary, it means it wasn't reserved or already unreserved.
            return False

    @cached_property
    def base_location(self) -> str:
        """
        Returns the normalized base directory for file storage.
        This property is cached after its first access.
        """
        return cast(
            str, os.path.normpath(self.value_or_setting(self._location, settings.media_root))
        )

    @cached_property
    def location(self) -> str:
        """
        Returns the absolute path of the file storage root directory.
        This property is cached after its first access.
        """
        return os.path.abspath(self.base_location)

    @cached_property
    def base_url(self) -> str:
        """
        Returns the base URL for accessing files in this storage. Ensures the URL
        ends with a slash. This property is cached after its first access.
        """
        if self._base_url is not None and not self._base_url.endswith("/"):
            self._base_url = f"{self._base_url}/"
        return self.value_or_setting(self._base_url, settings.media_url)

    @cached_property
    def file_permissions_mode(self) -> int:
        """
        Returns the numeric file permissions mode (e.g., 0o644) for new files.
        This property is cached after its first access.
        """
        return self.value_or_setting(self._file_permissions_mode, settings.file_upload_permissions)

    @cached_property
    def directory_permissions_mode(self) -> int:
        """
        Returns the numeric directory permissions mode (e.g., 0o755) for new directories.
        This property is cached after its first access.
        """
        return self.value_or_setting(
            self._directory_permissions_mode, settings.file_upload_directory_permissions
        )

    def _open(self, name: str, mode: str) -> File:
        """
        Internal method to open a file from the filesystem.

        Args:
            name (str): The name (path) of the file to open.
            mode (str): The mode in which to open the file (e.g., 'rb', 'wb').

        Returns:
            File: An Edgy `File` object wrapping the opened file stream.
        """
        # `open` returns a BinaryIO, which is compatible with `File`.
        return File(cast(BinaryIO, open(self.path(name), mode)))

    def _save(self, content: File, name: str) -> None:
        """
        Internal method to save the provided file content to the filesystem.
        It handles creating necessary directories, saving the content, and setting file permissions.

        Args:
            content (File): The file content to be saved, wrapped in an Edgy `File` object.
            name (str): The desired name (path relative to storage location) for the file.
        """
        full_path = self._get_full_path(name)
        self._create_directory(full_path)
        # _save_content might change `full_path` if there are `FileExistsError` conflicts.
        full_path = self._save_content(full_path, name, content)
        self._set_permissions(full_path)

    def _get_full_path(self, name: str) -> str:
        """
        Constructs the absolute filesystem path for a given file name.

        Args:
            name (str): The name (relative path) of the file.

        Returns:
            str: The absolute filesystem path.
        """
        return self.path(name)

    def _create_directory(self, full_path: str) -> None:
        """
        Ensures that all intermediate directories in the `full_path` exist.
        If they don't, they are created with the specified directory permissions.

        Args:
            full_path (str): The full path of the file, including its name.
        """
        directory = os.path.dirname(full_path)
        os.makedirs(directory, mode=self.directory_permissions_mode or 0o777, exist_ok=True)

    def _save_content(self, full_path: str, name: str, content: Any) -> str:
        """
        Saves the content to the specified full path. This method handles `FileExistsError`
        by generating an alternative filename and retrying, ensuring atomic writes where possible.

        Args:
            full_path (str): The initial full path where the file is attempted to be saved.
            name (str): The original desired name of the file (used for generating alternatives).
            content (Any): The content to be saved (can be a `File` or similar object with `chunks` or
            `temporary_file_path`).

        Returns:
            str: The final full path where the content was actually saved.
        """
        while True:
            try:
                # If the content has a temporary_file_path (e.g., from a file upload handler),
                # use atomic file move for efficiency and safety.
                if hasattr(content, "temporary_file_path"):
                    file_move_safe(content.temporary_file_path(), full_path)
                else:
                    # Otherwise, write content in chunks.
                    with open(full_path, "wb") as f:
                        for chunk in content.chunks():
                            f.write(chunk)
            except FileExistsError:
                # If a file with the same name already exists, generate a new available name
                # and update the full_path for the next attempt.
                name = self.get_available_name(name)
                full_path = self.path(name)
            else:
                # If save is successful (no FileExistsError), break the loop.
                break
        return full_path

    def _set_permissions(self, full_path: str) -> None:
        """
        Sets the file permissions for the newly saved file if `file_permissions_mode` is configured.

        Args:
            full_path (str): The absolute path of the saved file.
        """
        if self.file_permissions_mode is not None:
            os.chmod(full_path, self.file_permissions_mode)

    def _get_relative_path(self, full_path: str) -> str:
        """
        Calculates the relative path of a file from the storage's root location.
        Also attempts to ensure the file has the same group ID as the storage root on POSIX systems.

        Args:
            full_path (str): The absolute path of the file.

        Returns:
            str: The relative path, with backslashes replaced by forward slashes.
        """
        name = os.path.relpath(full_path, self.location)
        self._ensure_location_group_id(full_path)
        return str(name).replace("\\", "/")

    def _ensure_location_group_id(self, full_path: str) -> None:
        """
        On POSIX systems, attempts to change the group ID of the moved file
        to match that of the storage's root directory. This helps maintain
        consistent permissions for files managed by the storage.

        Args:
            full_path (str): The full path of the file.
        """
        if os.name == "posix":  # Only applies to POSIX-like systems
            file_gid = os.stat(full_path).st_gid
            location_gid = os.stat(self.location).st_gid
            if file_gid != location_gid:
                with contextlib.suppress(PermissionError):
                    # Attempt to change group ID, suppressing PermissionError if not allowed.
                    os.chown(full_path, uid=-1, gid=location_gid)

    def delete(self, name: str) -> None:
        """
        Deletes a file or an empty directory from the storage system.

        Args:
            name (str): The name (relative path) of the file or directory to delete.

        Raises:
            ValueError: If `name` is empty.
        """
        if not name:
            raise ValueError("The name must be given to delete().")

        full_path = self.path(name)
        try:
            if os.path.isdir(full_path):
                # Only empty directories can be removed with rmdir.
                os.rmdir(full_path)
            else:
                os.remove(full_path)
        except FileNotFoundError:
            # Silently ignore if the file/directory doesn't exist.
            pass

    def exists(self, name: str) -> bool:
        """
        Checks if a file or directory with the given name exists in the storage.

        Args:
            name (str): The name (relative path) of the file or directory.

        Returns:
            bool: True if the file or directory exists, False otherwise.
        """
        # `os.path.lexists` checks for existence of a path, including broken symbolic links.
        return os.path.lexists(self.path(name))

    def listdir(self, path: str) -> tuple[list[str], list[str]]:
        """
        Lists the contents of the specified path, separating them into directories and files.

        Args:
            path (str): The relative path within the storage to list.

        Returns:
            tuple: A 2-tuple containing two lists: the first list contains
                   directory names, and the second list contains file names.
        """
        path = self.path(path)  # Get the absolute path
        directories, files = [], []
        with os.scandir(path) as entries:
            for entry in entries:
                if entry.is_dir():
                    directories.append(entry.name)
                else:
                    files.append(entry.name)
        return directories, files

    def path(self, name: str) -> str:
        """
        Constructs the absolute filesystem path for a given name by joining it
        with the storage's base location.

        Args:
            name (str): The name (relative path) of the file or directory.

        Returns:
            str: The absolute filesystem path.
        """
        return safe_join(self.location, name)

    def size(self, name: str) -> int:
        """
        Returns the size of the file (in bytes) specified by the given name.

        Args:
            name (str): The name (relative path) of the file.

        Returns:
            int: The size of the file in bytes.
        """
        return os.path.getsize(self.path(name))

    def url(self, name: str) -> str:
        """
        Returns the absolute URL to access the file with the given name.
        Requires `base_url` to be set.

        Args:
            name (str): The name (relative path) of the file.

        Returns:
            str: The absolute URL of the file.

        Raises:
            ValueError: If `base_url` is not configured for this storage instance.
        """
        if self.base_url is None:
            raise ValueError("This file is not accessible via a URL.")
        url = filepath_to_uri(name)  # Convert path to URL-friendly format
        if url is not None:
            url = url.lstrip("/")  # Ensure no leading slash if it's already absolute
        # Join the base URL with the file's URL path.
        return urljoin(self.base_url, url)

    @staticmethod
    def _datetime_from_timestamp(ts: float) -> datetime:
        """
        Converts a UNIX timestamp (float) into a `datetime` object.
        The datetime will be timezone-aware if `settings.USE_TZ` is True.

        Args:
            ts (float): The UNIX timestamp.

        Returns:
            datetime: The corresponding `datetime` object.
        """
        tz = timezone.utc if settings.USE_TZ else None
        return datetime.fromtimestamp(ts, tz=tz)

    def get_accessed_time(self, name: str) -> datetime:
        """
        Returns the last accessed time (as a `datetime` object) of the file.
        The datetime will be timezone-aware if `settings.USE_TZ` is True.

        Args:
            name (str): The name (relative path) of the file.

        Returns:
            datetime: The last accessed time of the file.
        """
        return self._datetime_from_timestamp(os.path.getatime(self.path(name)))

    def get_created_time(self, name: str) -> datetime:
        """
        Returns the creation time (as a `datetime` object) of the file.
        The datetime will be timezone-aware if `settings.USE_TZ` is True.

        Args:
            name (str): The name (relative path) of the file.

        Returns:
            datetime: The creation time of the file.
        """
        return self._datetime_from_timestamp(os.path.getctime(self.path(name)))

    def get_modified_time(self, name: str) -> datetime:
        """
        Returns the last modified time (as a `datetime` object) of the file.
        The datetime will be timezone-aware if `settings.USE_TZ` is True.

        Args:
            name (str): The name (relative path) of the file.

        Returns:
            datetime: The last modified time of the file.
        """
        return self._datetime_from_timestamp(os.path.getmtime(self.path(name)))
