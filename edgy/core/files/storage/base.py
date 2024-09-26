import os
import pathlib
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, TypeVar, Union

from edgy.core.files.base import ContentFile, File
from edgy.exceptions import SuspiciousFileOperation
from edgy.utils.path import get_random_string, get_valid_filename, validate_file_name

_arg_val = TypeVar("_arg_val")
_arg_setting = TypeVar("_arg_setting")


class Storage(ABC):
    """
    The base storage that should be used
    to implement/override the default
    storage of Edgy.
    """

    # automatically set by handler
    name: str = ""

    # private helper
    @staticmethod
    def value_or_setting(value: _arg_val, setting: _arg_setting) -> Union[_arg_val, _arg_setting]:
        return setting if value is None else value

    @abstractmethod
    def _open(self, name: str, mode: str) -> Any: ...

    def open(self, name: str, mode: Union[str, None] = None) -> Any:
        if mode is None:
            mode = "rb"
        return self._open(name, mode)

    @abstractmethod
    def _save(self, content: "File", name: str = "") -> None: ...

    def save(self, content: Any, name: str = "") -> None:
        """
        Save new content to the file specified by name. The content should be
        a proper File object or any Python file-like object, ready to be read
        from the beginning.
        """
        if not name:
            name = content.name

        name = self.sanitize_name(name)

        if isinstance(content, str):
            content = ContentFile(content.encode("utf8"), name)
        elif isinstance(content, bytes):
            content = ContentFile(content, name)
        elif not hasattr(content, "chunks"):
            content = File(content, name)

        self._save(content, name)

    @abstractmethod
    def reserve_name(self, name: str) -> bool: ...

    @abstractmethod
    def unreserve_name(self, name: str) -> bool: ...

    def sanitize_name(self, name: str) -> str:
        """
        Return a filename, based on the provided filename, that's suitable for
        use in the target storage system.
        """
        validate_file_name(name, allow_relative_path=True)
        return get_valid_filename(name)

    def get_alternative_name(self, file_root: str, file_ext: str) -> str:
        """
        Return an alternative filename, by adding an underscore and a random 7
        character alphanumeric string (before the file extension, if one
        exists) to the filename.
        """
        return f"{file_root}_{get_random_string(7)}{file_ext}"

    def get_available_name(
        self,
        name: str,
        max_length: Union[int, None] = None,
        overwrite: bool = False,
        multi_process_safe: Union[bool] = None,
    ) -> str:
        """
        Return a filename that's free on the target storage system and
        available for new content to be written to.

        Args:
            name (str): The original filename.
            max_length (int, optional): The maximum length of the filename. Defaults to None.
            overwrite (bool, optional): Don't generate alternative names.

        Returns:
            str: The available filename. Need to call unreserve_name afterwards.

        Raises:
            SuspiciousFileOperation: If a path traversal attempt is detected or an available filename cannot be found.
        """
        if multi_process_safe is None:
            multi_process_safe = not overwrite
        name = str(name).replace("\\", "/")
        dir_name, file_name = os.path.split(name)

        if ".." in pathlib.PurePath(dir_name).parts:
            raise SuspiciousFileOperation(f"Detected path traversal attempt in '{dir_name}'")

        validate_file_name(file_name)
        file_root, file_ext = os.path.splitext(file_name)
        if multi_process_safe:
            # Ddd hexified process pid to prevent collisions among processes.
            # Adding proccess pid in front because it is most important to prevent classhes
            # among multiple processes.
            # Note: despite there is a thread id it is not always available and threads
            # often shortlived, so use a lock instead (see FilesystemStorage).
            file_root = f"{os.getpid() or 0:x}_{file_root}"

        while (max_length and len(name) > max_length) or (
            not self.reserve_name(name) and not overwrite
        ):
            if not overwrite:
                name = os.path.join(dir_name, self.get_alternative_name(file_root, file_ext))
            else:
                name = os.path.join(dir_name, f"{file_root}{file_ext}")

            if max_length is not None:
                truncation = len(name) - max_length
                if truncation > 0:
                    file_root = file_root[:-truncation]
                    if not file_root:
                        raise SuspiciousFileOperation(
                            f'Storage can not find an available filename for "{name}". '
                            "Please make sure that the corresponding file field "
                            'allows sufficient "max_length".'
                        )
                    if not overwrite:
                        name = os.path.join(
                            dir_name, self.get_alternative_name(file_root, file_ext)
                        )
                    else:
                        name = os.path.join(dir_name, f"{file_root}{file_ext}")

        return name

    def path(self, name: str) -> str:
        """
        Return a local filesystem path where the file can be retrieved using
        Python's built-in open() function. Storage systems that can't be
        accessed using open() should *not* implement this method.
        """
        raise NotImplementedError("This backend doesn't support absolute paths.")

    @abstractmethod
    def delete(self, name: str) -> None:
        """
        Delete the specified file from the storage system.
        """

    @abstractmethod
    def exists(self, name: str) -> bool:
        """
        Return True if a file referenced by the given name already exists in the
        storage system, or False if the name is available for a new file.
        """

    @abstractmethod
    def listdir(self, path: str) -> tuple[list[str], list[str]]:
        """
        List the contents of the specified path. Return a 2-tuple of lists:
        the first item being directories, the second item being files.
        """

    @abstractmethod
    def size(self, name: str) -> int:
        """
        Return the total size, in bytes, of the file specified by name.
        """

    def url(self, name: str) -> str:
        """
        Return an absolute URL where the file's contents can be accessed
        directly by a web browser.
        """
        raise NotImplementedError("This backend doesn't support 'url'.")

    def get_accessed_time(self, name: str) -> datetime:
        """
        Return the last accessed time (as a datetime) of the file specified by
        name. The datetime will be timezone-aware if USE_TZ=True.
        """
        raise NotImplementedError("This backend doesn't support 'accessed_time'.")

    def get_created_time(self, name: str) -> datetime:
        """
        Return the creation time (as a datetime) of the file specified by name.
        The datetime will be timezone-aware if USE_TZ=True.
        """
        raise NotImplementedError("This backend doesn't support 'created_time'.")

    def get_modified_time(self, name: str) -> datetime:
        """
        Return the last modified time (as a datetime) of the file specified by
        name. The datetime will be timezone-aware if USE_TZ=True.
        """
        raise NotImplementedError("This backend doesn't support 'modified_time'.")
