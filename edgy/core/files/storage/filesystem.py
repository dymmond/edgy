import contextlib
import os
from datetime import datetime, timezone
from functools import cached_property
from threading import Lock
from typing import Any, BinaryIO, Union, cast
from urllib.parse import urljoin

from edgy.conf import settings
from edgy.core.files.base import File
from edgy.core.files.move import file_move_safe
from edgy.utils.path import filepath_to_uri, safe_join

from .base import Storage


class FileSystemStorage(Storage):
    OS_OPEN_FLAGS = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)

    def __init__(
        self,
        location: Union[str, os.PathLike, None] = None,
        base_url: Union[str, None] = None,
        file_permissions_mode: Union[int, None] = None,
        directory_permissions_mode: Union[int, None] = None,
    ) -> None:
        self._location = location
        self._base_url = base_url
        self._file_permissions_mode = file_permissions_mode
        self._directory_permissions_mode = directory_permissions_mode
        self._name_lock = Lock()
        self._name_dict: dict[str, datetime] = {}

    def reserve_name(self, name: str) -> bool:
        with self._name_lock:
            # we may can have a timeout of a reservation
            if not self.exists(name) and name not in self._name_dict:
                self._name_dict[name] = datetime.now(timezone.utc)
                return True
        return False

    def unreserve_name(self, name: str) -> bool:
        try:
            with self._name_lock:
                del self._name_dict[name]
                return True
        except KeyError:
            return False

    @cached_property
    def base_location(self) -> str:
        return cast(
            str, os.path.normpath(self.value_or_setting(self._location, settings.media_root))
        )

    @cached_property
    def location(self) -> str:
        return os.path.abspath(self.base_location)

    @cached_property
    def base_url(self) -> str:
        if self._base_url is not None and not self._base_url.endswith("/"):
            self._base_url = f"{self._base_url}/"
        return self.value_or_setting(self._base_url, settings.media_url)

    @cached_property
    def file_permissions_mode(self) -> int:
        return self.value_or_setting(self._file_permissions_mode, settings.file_upload_permissions)

    @cached_property
    def directory_permissions_mode(self) -> int:
        return self.value_or_setting(
            self._directory_permissions_mode, settings.file_upload_directory_permissions
        )

    def _open(self, name: str, mode: str) -> File:
        return File(cast(BinaryIO, open(self.path(name), mode)))  # noqa: SIM115

    def _save(self, content: File, name: str) -> None:
        """
        Save the content to the given name.

        Args:
            name (str): The name of the file.
            content: The content to be saved.

        Returns:
            str: The saved file's relative path.
        """
        full_path = self._get_full_path(name)
        self._create_directory(full_path)
        full_path = self._save_content(full_path, name, content)
        self._set_permissions(full_path)

    def _get_full_path(self, name: str) -> str:
        """
        Get the full path for the given file name.

        Args:
            name (str): The name of the file.

        Returns:
            str: The full path of the file.
        """
        return self.path(name)

    def _create_directory(self, full_path: str) -> None:
        """
        Create any intermediate directories if they don't exist.

        Args:
            full_path (str): The full path of the file.
        """
        directory = os.path.dirname(full_path)
        os.makedirs(directory, mode=self.directory_permissions_mode or 0o777, exist_ok=True)

    def _save_content(self, full_path: str, name: str, content: Any) -> str:
        """
        Save the content to the given full path.

        Args:
            full_path (str): The full path of the file.
            content: The content to be saved.
        """
        while True:
            try:
                if hasattr(content, "temporary_file_path"):
                    file_move_safe(content.temporary_file_path(), full_path)
                else:
                    with open(full_path, "wb") as f:
                        for chunk in content.chunks():
                            f.write(chunk)
            except FileExistsError:
                name = self.get_available_name(name)
                full_path = self.path(name)
            else:
                break
        return full_path

    def _set_permissions(self, full_path: str) -> None:
        """
        Set permissions for the saved file.

        Args:
            full_path (str): The full path of the file.
        """
        if self.file_permissions_mode is not None:
            os.chmod(full_path, self.file_permissions_mode)

    def _get_relative_path(self, full_path: str) -> str:
        """
        Get the relative path of the file.

        Args:
            full_path (str): The full path of the file.

        Returns:
            str: The relative path of the file.
        """
        name = os.path.relpath(full_path, self.location)
        self._ensure_location_group_id(full_path)
        return str(name).replace("\\", "/")

    def _ensure_location_group_id(self, full_path: str) -> None:
        """
        Ensure the moved file has the same group ID as the storage root.

        Args:
            full_path (str): The full path of the file.
        """
        if os.name == "posix":
            file_gid = os.stat(full_path).st_gid
            location_gid = os.stat(self.location).st_gid
            if file_gid != location_gid:
                with contextlib.suppress(PermissionError):
                    os.chown(full_path, uid=-1, gid=location_gid)

    def delete(self, name: str) -> None:
        """
        Delete the file or directory with the given name.

        Args:
            name (str): The name of the file or directory to be deleted.

        Raises:
            ValueError: If the name is empty.
        """
        if not name:
            raise ValueError("The name must be given to delete().")

        full_path = self.path(name)
        try:
            if os.path.isdir(full_path):
                os.rmdir(full_path)
            else:
                os.remove(full_path)
        except FileNotFoundError:
            ...

    def exists(self, name: str) -> bool:
        """
        Check if the given file or directory exists.

        Args:
            name (str): The name of the file or directory.

        Returns:
            bool: True if the file or directory exists, False otherwise.
        """
        return os.path.lexists(self.path(name))

    def listdir(self, path: str) -> tuple[list[str], list[str]]:
        """
        List directories and files in the given path.

        Args:
            path (str): The path to list directories and files from.

        Returns:
            tuple: A tuple containing lists of directories and files.
        """
        path = self.path(path)
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
        Get the absolute path of the given name relative to the storage location.

        Args:
            name (str): The name of the file or directory.

        Returns:
            str: The absolute path.
        """
        return safe_join(self.location, name)

    def size(self, name: str) -> int:
        """
        Return the size, in bytes, of the file specified by the name.

        Args:
            name (str): The name of the file.

        Returns:
            int: The size of the file in bytes.
        """
        return os.path.getsize(self.path(name))

    def url(self, name: str) -> str:
        """
        Return the URL to access the file with the given name.

        Args:
            name (str): The name of the file.

        Returns:
            str: The URL of the file.

        Raises:
            ValueError: If base_url is not set.
        """
        if self.base_url is None:
            raise ValueError("This file is not accessible via a URL.")
        url = filepath_to_uri(name)
        if url is not None:
            url = url.lstrip("/")
        return urljoin(self.base_url, url)

    @staticmethod
    def _datetime_from_timestamp(ts: float) -> datetime:
        """
        Convert a UNIX timestamp to a datetime object.

        Args:
            ts (float): The UNIX timestamp.

        Returns:
            datetime: The corresponding datetime object.
        """
        tz = timezone.utc if settings.USE_TZ else None
        return datetime.fromtimestamp(ts, tz=tz)

    def get_accessed_time(self, name: str) -> datetime:
        """
        Return the last accessed time of the file specified by the name.

        Args:
            name (str): The name of the file.

        Returns:
            datetime: The last accessed time of the file.
        """
        return self._datetime_from_timestamp(os.path.getatime(self.path(name)))

    def get_created_time(self, name: str) -> datetime:
        """
        Return the creation time of the file specified by the name.

        Args:
            name (str): The name of the file.

        Returns:
            datetime: The creation time of the file.
        """
        return self._datetime_from_timestamp(os.path.getctime(self.path(name)))

    def get_modified_time(self, name: str) -> datetime:
        """
        Return the last modified time of the file specified by the name.

        Args:
            name (str): The name of the file.

        Returns:
            datetime: The last modified time of the file.
        """
        return self._datetime_from_timestamp(os.path.getmtime(self.path(name)))
