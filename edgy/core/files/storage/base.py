import os
import pathlib
from typing import Any, Union

from edgy.core.files.base import File
from edgy.exceptions import SuspiciousFileOperation
from edgy.utils.text import get_random_string, get_valid_filename, validate_file_name


class Storage:
    """
    The base storage that should be used
    to implement/override the default
    storage of Edgy.
    """

    def open(self, name: str, mode: Union[str, None] = None) -> Any:
        if mode is None:
            mode = "rb"
        return self._open(name, mode)

    def save(self, name: str, content: Any, max_length: Union[int, None] = None) -> str:
        """
        Save new content to the file specified by name. The content should be
        a proper File object or any Python file-like object, ready to be read
        from the beginning.
        """
        if name is None:
            name = content.name

        if not hasattr(content, "chunks"):
            content = File(content, name)

        name = self.get_available_name(name, max_length=max_length)
        name = self._save(name, content)
        validate_file_name(name, allow_relative_path=True)
        return name

    def get_valid_name(self, name: str) -> str:
        """
        Return a filename, based on the provided filename, that's suitable for
        use in the target storage system.
        """
        return get_valid_filename(name)

    def get_alternative_name(self, file_root: str, file_ext: str) -> str:
        """
        Return an alternative filename, by adding an underscore and a random 7
        character alphanumeric string (before the file extension, if one
        exists) to the filename.
        """
        return f"{file_root}_{get_random_string(7)}{file_ext}"

    def get_available_name(self, name: str, max_length: Union[int, None] = None) -> str:
        """
        Return a filename that's free on the target storage system and
        available for new content to be written to.

        Args:
            name (str): The original filename.
            max_length (int, optional): The maximum length of the filename. Defaults to None.

        Returns:
            str: The available filename.

        Raises:
            SuspiciousFileOperation: If a path traversal attempt is detected or an available filename cannot be found.
        """
        name = str(name).replace("\\", "/")
        dir_name, file_name = os.path.split(name)

        if ".." in pathlib.PurePath(dir_name).parts:
            raise SuspiciousFileOperation(f"Detected path traversal attempt in '{dir_name}'")

        validate_file_name(file_name)
        file_root, file_ext = os.path.splitext(file_name)

        while self.exists(name) or (max_length and len(name) > max_length):
            name = os.path.join(dir_name, self.get_alternative_name(file_root, file_ext))

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
                    name = os.path.join(dir_name, self.get_alternative_name(file_root, file_ext))

        return name

    def generate_filename(self, filename: str) -> str:
        """
        Validate the filename and return a normalized filename to be passed to the save() method.

        Args:
            filename (str): The original filename.

        Returns:
            str: The normalized filename.

        Raises:
            SuspiciousFileOperation: If a path traversal attempt is detected in the filename.
        """
        filename = str(filename).replace("\\", "/")
        dirname, filename = os.path.split(filename)
        if ".." in pathlib.PurePath(dirname).parts:
            raise SuspiciousFileOperation(f"Detected path traversal attempt in '{dirname}'")

        return os.path.normpath(os.path.join(dirname, self.get_valid_name(filename)))

    def path(self, name: str) -> Any:
        """
        Return a local filesystem path where the file can be retrieved using
        Python's built-in open() function. Storage systems that can't be
        accessed using open() should *not* implement this method.
        """
        raise NotImplementedError("This backend doesn't support absolute paths.")

    def delete(self, name: str) -> Any:
        """
        Delete the specified file from the storage system.
        """
        raise NotImplementedError("subclasses of Storage must provide a delete() method")

    def exists(self, name: str) -> Any:
        """
        Return True if a file referenced by the given name already exists in the
        storage system, or False if the name is available for a new file.
        """
        raise NotImplementedError("subclasses of Storage must provide an exists() method")

    def listdir(self, path: str) -> Any:
        """
        List the contents of the specified path. Return a 2-tuple of lists:
        the first item being directories, the second item being files.
        """
        raise NotImplementedError("subclasses of Storage must provide a listdir() method")

    def size(self, name: str) -> Any:
        """
        Return the total size, in bytes, of the file specified by name.
        """
        raise NotImplementedError("subclasses of Storage must provide a size() method")

    def url(self, name: str) -> Any:
        """
        Return an absolute URL where the file's contents can be accessed
        directly by a web browser.
        """
        raise NotImplementedError("subclasses of Storage must provide a url() method")

    def get_accessed_time(self, name: str) -> Any:
        """
        Return the last accessed time (as a datetime) of the file specified by
        name. The datetime will be timezone-aware if USE_TZ=True.
        """
        raise NotImplementedError(
            "subclasses of Storage must provide a get_accessed_time() method"
        )

    def get_created_time(self, name: str) -> Any:
        """
        Return the creation time (as a datetime) of the file specified by name.
        The datetime will be timezone-aware if USE_TZ=True.
        """
        raise NotImplementedError("subclasses of Storage must provide a get_created_time() method")

    def get_modified_time(self, name: str) -> Any:
        """
        Return the last modified time (as a datetime) of the file specified by
        name. The datetime will be timezone-aware if USE_TZ=True.
        """
        raise NotImplementedError(
            "subclasses of Storage must provide a get_modified_time() method"
        )
