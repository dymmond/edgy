import os
import pathlib
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, TypeVar

from edgy.core.files.base import ContentFile, File
from edgy.exceptions import SuspiciousFileOperation
from edgy.utils.path import get_random_string, get_valid_filename, validate_file_name

# Type variable for a generic argument value.
_arg_val = TypeVar("_arg_val")
# Type variable for a generic setting value.
_arg_setting = TypeVar("_arg_setting")


class Storage(ABC):
    """
    The abstract base class for file storage backends in Edgy.

    All custom storage implementations should inherit from this class and
    implement its abstract methods to provide concrete functionality for
    file operations (opening, saving, deleting, checking existence, listing
    directories, and getting file size).

    Attributes:
        name (str): Automatically set by the handler, represents the name of the storage.
    """

    # automatically set by handler
    name: str = ""

    # private helper
    @staticmethod
    def value_or_setting(value: _arg_val, setting: _arg_setting) -> _arg_val | _arg_setting:
        """
        Helper method to return a `value` if it's not None, otherwise return a `setting`.
        This is useful for providing defaults from settings if no explicit value is given.

        Args:
            value (_arg_val): The explicit value to check.
            setting (_arg_setting): The default setting to use if `value` is None.

        Returns:
            _arg_val | _arg_setting: The `value` if not None, else the `setting`.
        """
        return setting if value is None else value

    @abstractmethod
    def _open(self, name: str, mode: str) -> Any:
        """
        Abstract method to open a file from the storage system.
        Concrete storage implementations must provide their specific logic here.

        Args:
            name (str): The name (path) of the file to open.
            mode (str): The mode in which to open the file (e.g., 'rb', 'wb').

        Returns:
            Any: A file-like object specific to the storage backend.
        """
        ...

    def open(self, name: str, mode: str | None = None) -> Any:
        """
        Opens a file from the storage system. This is a public wrapper that
        calls the `_open` abstract method, providing a default mode if none is specified.

        Args:
            name (str): The name (path) of the file to open.
            mode (str | None): The mode in which to open the file. Defaults to 'rb'.

        Returns:
            Any: A file-like object specific to the storage backend.
        """
        if mode is None:
            mode = "rb"
        return self._open(name, mode)

    @abstractmethod
    def _save(self, content: "File", name: str = "") -> None:
        """
        Abstract method to save content to the storage system.
        Concrete storage implementations must provide their specific logic here.

        Args:
            content ("File"): The content to save, encapsulated in an Edgy `File` object.
            name (str): The desired name (path) for the saved file.
        """
        ...

    def save(self, content: Any, name: str = "") -> None:
        """
        Saves new content to the file specified by `name`. The `content` can be
        a raw string, bytes, a Python file-like object, or an Edgy `File` object.
        This method handles converting various content types into a standardized
        `File` object before calling the `_save` abstract method.

        Args:
            content (Any): The content to be saved. Can be `str`, `bytes`,
                           a file-like object, or an Edgy `File`.
            name (str): The desired name (path) for the saved file. If empty,
                        the `name` attribute of the `content` object is used.
        """
        if not name:
            name = content.name

        name = self.sanitize_name(name)

        # Convert various content types into an Edgy File object.
        if isinstance(content, str):
            # Encode string content to bytes and wrap in ContentFile.
            content = ContentFile(content.encode("utf8"), name)
        elif isinstance(content, bytes):
            # Wrap bytes content in ContentFile.
            content = ContentFile(content, name)
        elif not hasattr(content, "chunks"):
            # If it's a file-like object but not an Edgy File (lacks 'chunks'), wrap it.
            content = File(content, name)

        self._save(content, name)

    @abstractmethod
    def reserve_name(self, name: str) -> bool:
        """
        Abstract method to reserve a filename in a multi-process/multi-thread safe manner.
        This prevents other processes/threads from using the same name concurrently.

        Args:
            name (str): The filename to reserve.

        Returns:
            bool: True if the name was successfully reserved, False otherwise.
        """
        ...

    @abstractmethod
    def unreserve_name(self, name: str) -> bool:
        """
        Abstract method to unreserve a previously reserved filename.
        This should be called after a file operation (like `save`) is completed
        or aborted, to release the reserved name.

        Args:
            name (str): The filename to unreserve.

        Returns:
            bool: True if the name was successfully unreserved, False otherwise.
        """
        ...

    def sanitize_name(self, name: str) -> str:
        """
        Returns a filename, based on the provided filename, that is suitable for
        use in the target storage system. This method performs validation and
        sanitization to ensure the name is safe and valid.

        Args:
            name (str): The original filename.

        Returns:
            str: The sanitized filename.
        """
        # Validate for path traversal attempts and other unsafe characters.
        validate_file_name(name, allow_relative_path=True)
        # Further sanitize the name to be valid for the filesystem.
        return get_valid_filename(name)

    def get_alternative_name(self, file_root: str, file_ext: str) -> str:
        """
        Generates an alternative filename by appending an underscore and a random
        7-character alphanumeric string before the file extension. This is used
        when an original filename already exists and `overwrite` is False.

        Args:
            file_root (str): The base name of the file (without extension).
            file_ext (str): The file extension (including the dot, e.g., ".txt").

        Returns:
            str: An alternative filename.
        """
        return f"{file_root}_{get_random_string(7)}{file_ext}"

    def get_available_name(
        self,
        name: str,
        max_length: int | None = None,
        overwrite: bool = False,
        multi_process_safe: bool | None = None,
    ) -> str:
        """
        Returns a filename that is free on the target storage system and
        available for new content to be written to. This method handles
        name conflicts by generating alternative names if `overwrite` is False.
        It also incorporates multi-process safety mechanisms.

        Args:
            name (str): The original filename.
            max_length (int, optional): The maximum allowed length for the filename.
                                        If the generated name exceeds this, it will be
                                        truncated. Defaults to None.
            overwrite (bool, optional): If True, existing files with the same name
                                        will be overwritten without generating an
                                        alternative name. Defaults to False.
            multi_process_safe (bool, optional): If True, a process ID will be
                                                 added to the filename to prevent
                                                 collisions among multiple processes.
                                                 If None, it defaults to `not overwrite`.
                                                 Defaults to None.

        Returns:
            str: The available filename. Call `unreserve_name` after using this name.

        Raises:
            SuspiciousFileOperation:
                - If a path traversal attempt is detected in the directory name.
                - If an available filename cannot be found after truncation attempts.
        """
        if multi_process_safe is None:
            multi_process_safe = not overwrite
        # Normalize path separators.
        name = str(name).replace("\\", "/")
        dir_name, file_name = os.path.split(name)

        # Check for path traversal attempts in the directory component.
        if ".." in pathlib.PurePath(dir_name).parts:
            raise SuspiciousFileOperation(f"Detected path traversal attempt in '{dir_name}'")

        # Sanitize the file name component.
        validate_file_name(file_name)
        file_root, file_ext = os.path.splitext(file_name)

        if multi_process_safe:
            # Add a hexified process PID to prevent collisions among processes.
            # The PID is added at the front as it's crucial for inter-process collision prevention.
            # Note: Thread IDs are not always available and threads are often short-lived,
            # so a lock mechanism should be used for thread safety (e.g., in FilesystemStorage).
            file_root = f"{os.getpid() or 0:x}_{file_root}"

        # Loop until an available name is found or an error occurs.
        while (max_length and len(name) > max_length) or (
            not self.reserve_name(name) and not overwrite
        ):
            if not overwrite:
                # Generate an alternative name if not overwriting.
                name = os.path.join(dir_name, self.get_alternative_name(file_root, file_ext))
            else:
                # If overwriting, reuse the original name (potentially truncated).
                name = os.path.join(dir_name, f"{file_root}{file_ext}")

            if max_length is not None:
                # If max_length is specified, check for truncation.
                truncation = len(name) - max_length
                if truncation > 0:
                    # Truncate the file root if the name exceeds max_length.
                    file_root = file_root[:-truncation]
                    if not file_root:
                        # If file_root becomes empty after truncation, raise an error.
                        raise SuspiciousFileOperation(
                            f'Storage can not find an available filename for "{name}". '
                            "Please make sure that the corresponding file field "
                            'allows sufficient "max_length".'
                        )
                    # Regenerate the name with the truncated file_root.
                    if not overwrite:
                        name = os.path.join(
                            dir_name, self.get_alternative_name(file_root, file_ext)
                        )
                    else:
                        name = os.path.join(dir_name, f"{file_root}{file_ext}")

        return name

    def path(self, name: str) -> str:
        """
        Returns a local filesystem path where the file can be retrieved using
        Python's built-in `open()` function. Storage systems that cannot be
        accessed directly via a local path (e.g., cloud storage) should
        raise `NotImplementedError`.

        Args:
            name (str): The name (path) of the file.

        Returns:
            str: The local filesystem path to the file.

        Raises:
            NotImplementedError: If the backend does not support absolute local paths.
        """
        raise NotImplementedError("This backend doesn't support absolute paths.")

    @abstractmethod
    def delete(self, name: str) -> None:
        """
        Abstract method to delete the specified file from the storage system.
        Concrete storage implementations must provide their specific logic here.

        Args:
            name (str): The name (path) of the file to delete.
        """
        ...

    @abstractmethod
    def exists(self, name: str) -> bool:
        """
        Abstract method to check if a file referenced by the given name already
        exists in the storage system.

        Args:
            name (str): The name (path) of the file to check.

        Returns:
            bool: True if the file exists, False otherwise.
        """
        ...

    @abstractmethod
    def listdir(self, path: str) -> tuple[list[str], list[str]]:
        """
        Abstract method to list the contents of the specified path within the storage system.

        Args:
            path (str): The path to list.

        Returns:
            tuple[list[str], list[str]]: A 2-tuple where the first list contains
                                        directory names and the second list contains
                                        file names within the specified path.
        """
        ...

    @abstractmethod
    def size(self, name: str) -> int:
        """
        Abstract method to return the total size, in bytes, of the file specified by name.

        Args:
            name (str): The name (path) of the file.

        Returns:
            int: The size of the file in bytes.
        """
        ...

    def url(self, name: str) -> str:
        """
        Returns an absolute URL where the file's contents can be accessed
        directly by a web browser. Storage systems that do not provide
        direct URL access (e.g., local filesystem without a web server)
        should raise `NotImplementedError`.

        Args:
            name (str): The name (path) of the file.

        Returns:
            str: The absolute URL to the file.

        Raises:
            NotImplementedError: If the backend does not support direct URLs.
        """
        raise NotImplementedError("This backend doesn't support 'url'.")

    def get_accessed_time(self, name: str) -> datetime:
        """
        Returns the last accessed time (as a timezone-aware `datetime` object)
        of the file specified by name.

        Args:
            name (str): The name (path) of the file.

        Returns:
            datetime: The last accessed time.

        Raises:
            NotImplementedError: If the backend does not support retrieving accessed time.
        """
        raise NotImplementedError("This backend doesn't support 'accessed_time'.")

    def get_created_time(self, name: str) -> datetime:
        """
        Returns the creation time (as a timezone-aware `datetime` object)
        of the file specified by name.

        Args:
            name (str): The name (path) of the file.

        Returns:
            datetime: The creation time.

        Raises:
            NotImplementedError: If the backend does not support retrieving creation time.
        """
        raise NotImplementedError("This backend doesn't support 'created_time'.")

    def get_modified_time(self, name: str) -> datetime:
        """
        Returns the last modified time (as a timezone-aware `datetime` object)
        of the file specified by name.

        Args:
            name (str): The name (path) of the file.

        Returns:
            datetime: The last modified time.

        Raises:
            NotImplementedError: If the backend does not support retrieving modified time.
        """
        raise NotImplementedError("This backend doesn't support 'modified_time'.")
