import os
import sys
from functools import cached_property
from io import BytesIO
from typing import (
    TYPE_CHECKING,
    Any,
    BinaryIO,
    Callable,
    Generator,
    Literal,
    Optional,
    Tuple,
    Union,
    cast,
)

if TYPE_CHECKING:
    from .storage import Storage

if sys.version_info >= (3, 10):  # pragma: no cover
    from typing import ParamSpec
else:  # pragma: no cover
    from typing_extensions import ParamSpec

if TYPE_CHECKING:
    from edgy.core.db.fields.types import BaseFieldType
    from edgy.core.db.models.types import BaseModelType


P = ParamSpec("P")


def _get_storage(storage: str) -> "Storage":
    from .storage import storages

    return storages[storage]


class File:
    name: str
    file: Optional[BinaryIO]
    storage: "Storage"

    def __init__(
        self,
        file: Optional[BinaryIO] = None,
        name: str = "",
        storage: Union["Storage", str, None] = None,
    ) -> None:
        self.file = file
        if not storage:
            storage = "default"
        if isinstance(storage, str):
            storage = _get_storage(storage)

        self.storage = storage

        if not name:
            name = getattr(file, "name", "")

        self.name = name or ""

        if hasattr(file, "mode"):
            self.mode = file.mode  # type: ignore

    def __eq__(self, other: Union[str, "File"]) -> bool:
        if hasattr(other, "name"):
            return self.name == other.name
        return self.name == other

    def __hash__(self) -> int:
        return hash(self._name)

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self or 'None'}>"

    def __bool__(self) -> bool:
        return bool(self.name or self.file is not None)

    @cached_property
    def size(self) -> int:
        assert self.file is not None, "File is closed"
        if hasattr(self.file, "size"):
            return cast(int, self.file.size)
        if hasattr(self.file, "name"):
            try:
                return self.storage.size(self.file.name)
            except (OSError, TypeError):
                pass
        if hasattr(self.file, "tell") and hasattr(self.file, "seek"):
            pos = self.file.tell()
            self.file.seek(0, os.SEEK_END)
            size = self.file.tell()
            self.file.seek(pos)
            return size
        raise AttributeError("Unable to determine the file's size.")

    def __len__(self) -> int:
        return self.size

    @property
    def closed(self) -> bool:
        """Return True if the file is closed."""
        return not self.file or self.file.closed

    @property
    def path(self) -> str:
        assert self.file is not None, "File is closed"
        return self.storage.path(self.name)

    @property
    def url(self) -> str:
        return self.storage.url(self.name)

    def readable(self) -> bool:
        """Return True if the file is readable."""
        if self.closed:
            return False
        assert self.file is not None
        if hasattr(self.file, "readable"):
            return self.file.readable()
        return True

    def writable(self) -> bool:
        """Return True if the file is writable."""
        if self.closed:
            return False
        assert self.file is not None
        if hasattr(self.file, "writable"):
            return self.file.writable()
        return "w" in getattr(self.file, "mode", "")

    def seekable(self) -> bool:
        """Return True if the file is seekable."""
        if self.closed:
            return False
        assert self.file is not None
        if hasattr(self.file, "seekable"):
            return self.file.seekable()
        return True

    def chunks(self, chunk_size: Union[int, None] = None) -> Generator[bytes, None, None]:
        """
        Read the file and yield chunks of ``chunk_size`` bytes (defaults to
        ``File.DEFAULT_CHUNK_SIZE``).

        Args:
            chunk_size (int, optional): The size of each chunk in bytes. Defaults to None.

        Yields:
            bytes: Data read from the file.

        Raises:
            AttributeError: If unable to seek to the beginning of the file.
        """
        assert self.file is not None, "File is closed"
        chunk_size = chunk_size or self.DEFAULT_CHUNK_SIZE

        try:
            self.file.seek(0)
        except (AttributeError, OSError):
            ...
        else:
            while True:
                data = self.read(chunk_size)
                if not data:
                    break
                yield data

    def multiple_chunks(self, chunk_size: Union[int, None] = None) -> bool:
        """
        Return ``True`` if you can expect multiple chunks.

        Args:
            chunk_size (int, optional): The size of each chunk in bytes. Defaults to None.

        Returns:
            bool: True if the file can be expected to have multiple chunks, False otherwise.
        """
        if chunk_size is None:
            chunk_size = self.DEFAULT_CHUNK_SIZE

        return self.size > chunk_size

    def __enter__(self) -> "File":
        assert self.file is not None, "File is closed"
        return self

    def __exit__(self, exc_type: Exception, exc_value: Any, tb: Any) -> None:
        self.close()

    def open(self, mode: Union[str, None] = None) -> "File":
        """
        Open the file with the specified mode.

        Args:
            mode (str, optional): The mode in which to open the file. If not provided, uses the existing mode.
            *args: Positional arguments to be passed to the `open` function.
            **kwargs: Keyword arguments to be passed to the `open` function.

        Returns:
            File: The opened file.

        Raises:
            ValueError: If the file cannot be reopened.
        """
        if not self.closed:
            self.seek(0)
        elif self.name and self.storage.exists(self.name):
            self.file = self.storage.open(self.name, mode or self.mode)  # noqa: SIM115
        else:
            raise ValueError("The file cannot be reopened.")

        return self

    def close(self) -> None:
        if self.file is None:
            return
        self.file.close()
        self.file = None


class ContentFile(File):
    file: BinaryIO

    def __init__(self, content: bytes, name: str = ""):
        super().__init__(file=BytesIO(content), name=name)
        self.size = len(content)

    def __str__(self) -> str:
        return "Raw content"

    def open(self, mode: Union[str, Any] = None) -> "ContentFile":
        self.seek(0)
        return self

    def close(self) -> None: ...

    def write(self, data: bytes) -> int:
        self.__dict__.pop("size", None)
        return self.file.write(data)


class FieldFile(File):
    operation: Literal["none", "save", "save_delete", "delete"] = "none"
    old: Optional[Tuple["Storage", str]] = None
    instance: Optional["BaseModelType"] = None

    def __init__(
        self,
        field: "BaseFieldType",
        content: Union[BinaryIO, bytes, None, File] = None,
        name: str = "",
        size: Optional[int] = None,
        storage: Union["Storage", str, None] = None,
        generate_name_fn: Optional[Callable[["BaseModelType", str], str]] = None,
    ) -> None:
        if isinstance(content, File):
            content = content.open("rb").file
        elif isinstance(content, bytes):
            content = BytesIO(content)
        super().__init__(content, name=name, storage=storage)
        self.field = field
        self.generate_name_fn = generate_name_fn

    def _require_file(self) -> None:
        if self.file is None or not self.name:
            raise ValueError(f"The '{self.field.name}' attribute has no file associated with it.")

    async def execute_operation(self) -> None:
        if self.operation == "save" or self.operation == "save_delete":
            if self.file is None or not self.name:
                raise ValueError(
                    f"The '{self.field.name}' attribute has no file associated with it."
                )
            try:
                self.storage.save(self.file, self.name)
            finally:
                self.storage.unreserve_name(self.name)
            if self.operation == "save_delete" and self.old is not None:
                self.old[0].delete(self.old[1])
        elif self.operation == "delete":
            if hasattr(self, "file"):
                self.close()
            self.storage.delete(self.name)
        self.operation = "none"
        self.old = None

    def save(
        self,
        content: Union[BinaryIO, bytes, None, File],
        name: str = "",
        delete_old: bool = True,
        storage: Optional["Storage"] = None,
    ) -> None:
        """
        Save the file to storage and update associated model fields.

        Args:
            name (str): The name of the file.
            content: The file content.
        """
        if content is None:
            self.delete()
            return
        elif isinstance(content, File):
            content = content.open("rb").file
        elif isinstance(content, bytes):
            content = BytesIO(content)

        if not name:
            name = getattr(content, "name", "")

        # Generate filename based on instance and name
        if self.generate_name_fn is not None:
            name = self.generate_name_fn(self.instance, name)

        if storage is None:
            storage = self.storage

        name = storage.get_available_name(name, max_length=getattr(self.field, "max_length", None))
        if hasattr(self, "file"):
            self.close()
        self.old = (self.storage, self.name)
        self.storage = storage
        self.name = name
        self.operation = "save_delete" if delete_old else "save"

    def reset(self) -> None:
        """
        Reset staged file operation.
        """
        if self.operation == "save" or self.operation == "save_delete":
            if hasattr(self, "file"):
                self.close()
            self.storage.unreserve_name(self.name)
        if self.old is not None:
            self.storage, self.name = self.old
            self.old = None
        self.operation = "none"

    def delete(self) -> None:
        """
        Mark the file associated with this object for deletion from storage.
        """
        if not self:
            return
        self.reset()
        self.operation = "delete"
