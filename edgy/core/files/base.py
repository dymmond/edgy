from __future__ import annotations

import asyncio
import os
from collections.abc import Callable, Generator, Sequence
from copy import copy
from functools import cached_property
from io import BytesIO
from typing import (
    TYPE_CHECKING,
    Any,
    BinaryIO,
    ClassVar,
    Literal,
    ParamSpec,
    cast,
)

from pydantic import Base64Bytes, BaseModel, ConfigDict, Field

from edgy.exceptions import FileOperationError, SuspiciousFileOperation

if TYPE_CHECKING:
    # Import Storage for type hinting, avoiding circular imports at runtime.
    from .storage import Storage

if TYPE_CHECKING:
    # Conditional import for Pillow's ImageFile, only for type checking.
    from PIL.ImageFile import ImageFile  # pyright: ignore[reportMissingImports]

    # Imports for Edgy's internal field and model types.
    from edgy.core.db.fields.types import BaseFieldType
    from edgy.core.db.models.types import BaseModelType


# ParamSpec for generic callable types.
P = ParamSpec("P")


def _get_storage(storage: str) -> Storage:
    """
    Helper function to retrieve a storage instance by its alias.

    Args:
        storage (str): The alias of the storage.

    Returns:
        Storage: The storage instance.
    """
    from .storage import storages  # Import here to avoid circular dependency

    return storages[storage]


class FileStruct(BaseModel):
    """
    A Pydantic model representing the structure of a file for API consumption,
    especially for handling file uploads via base64 encoding.
    """

    model_config = ConfigDict(extra="forbid")  # Disallow extra fields
    name: str = Field(min_length=1)  # File name, must not be empty
    content: Base64Bytes  # File content, base64 encoded bytes


class File:
    """
    Represents a file managed by an Edgy storage backend. This class provides
    an abstraction over actual file objects or paths, allowing interaction
    with files regardless of their underlying storage location (local, S3, etc.).

    It encapsulates file properties like name, size, and offers methods for
    reading, writing, and closing the file, as well as interacting with its storage.
    """

    name: str  # The name (path) of the file relative to the storage root.
    file: BinaryIO | None  # The underlying Python binary file-like object.
    storage: Storage  # The storage backend responsible for this file.
    DEFAULT_CHUNK_SIZE: ClassVar[int] = 64 * 2**10  # Default chunk size for reading (64 KB).
    mode: str = "rb"  # Default mode for opening the file.

    def __init__(
        self,
        file: BinaryIO | bytes | None | File = None,
        name: str = "",
        storage: Storage | str | None = None,
    ) -> None:
        """
        Initializes a File instance.

        Args:
            file (BinaryIO | bytes | None | File): The actual file content. Can be:
                - A binary file-like object (e.g., from `open()`).
                - Raw bytes content.
                - Another `File` instance (will open its underlying file).
                - None (for a file that doesn't yet have content).
            name (str): The desired name (path) of the file within the storage.
                        If not provided, attempts to infer from `file.name`.
            storage (Storage | str | None): The storage backend to use. Can be a
                                            `Storage` instance or its alias (string).
                                            If None, "default" storage is used.
        """
        # If `file` is another File instance, open its underlying file.
        if isinstance(file, File):
            file = file.open("rb").file
        # If `file` is raw bytes, wrap it in a BytesIO stream.
        elif isinstance(file, bytes):
            file = BytesIO(file)
        self.file = file

        # Determine the storage backend.
        if not storage:
            storage = "default"  # Use default storage if not specified.
        if isinstance(storage, str):
            # If a string alias is given, retrieve the actual Storage instance.
            storage = _get_storage(storage)
        self.storage = storage

        # Determine the file name.
        if not name:
            name = getattr(file, "name", "")  # Try to get name from file object.
        self.name = name or ""  # Ensure name is a string, even if empty.
        assert isinstance(self.name, str)

        # Infer file mode if available from the underlying file object.
        if hasattr(file, "mode"):
            self.mode = file.mode

    def __eq__(self, other: str | File) -> bool:
        """Compares two File instances or a File instance with a string by their names."""
        if hasattr(other, "name"):
            return self.name == other.name
        return self.name == other

    def __hash__(self) -> int:
        """Returns the hash of the file's name."""
        return hash(self._name)  # Assuming _name exists or is a typo for self.name

    def __str__(self) -> str:
        """Returns the file's name as its string representation."""
        return self.name

    def __repr__(self) -> str:
        """Returns a developer-friendly representation of the File instance."""
        return f"<{type(self).__name__}: {self or 'None'}>"

    def __bool__(self) -> bool:
        """
        Evaluates to True if the file has a name or an associated file object,
        False otherwise.
        """
        return bool(self.name or self.file is not None)

    @cached_property
    def size(self) -> int:
        """
        Returns the size of the file in bytes.
        This property is cached after its first access. It attempts to determine
        the size in several ways:
        1. From `file.size` if available.
        2. From `storage.size` if the file has a name.
        3. By seeking to the end of the file object and telling its position.

        Raises:
            AttributeError: If unable to determine the file's size by any method.
        """
        if self.file is None:
            return 0
        if hasattr(self.file, "size"):
            return cast(int, self.file.size)
        if hasattr(self.file, "name"):
            try:
                return self.storage.size(self.file.name)
            except (OSError, TypeError, SuspiciousFileOperation):
                # Ignore SuspiciousFileOperation if the file reference might be outside
                # the expected media folder, allowing size determination from other means.
                pass
        if hasattr(self.file, "tell") and hasattr(self.file, "seek"):
            pos = self.file.tell()  # Store current position
            self.file.seek(0, os.SEEK_END)  # Seek to end
            size = self.file.tell()  # Get size
            self.file.seek(pos)  # Restore original position
            return size
        raise AttributeError("Unable to determine the file's size.")

    def __len__(self) -> int:
        """Returns the size of the file, equivalent to `self.size`."""
        return self.size

    @property
    def closed(self) -> bool:
        """Returns True if the underlying file object is closed or None."""
        return not self.file or self.file.closed

    @property
    def path(self) -> str:
        """Returns the absolute filesystem path of the file (if supported by storage)."""
        return self.storage.path(self.name)

    @property
    def url(self) -> str:
        """Returns the public URL of the file (if supported by storage)."""
        return self.storage.url(self.name)

    def chunks(self, chunk_size: int | None = None) -> Generator[bytes, None, None]:
        """
        Reads the file content in chunks of a specified size.

        Args:
            chunk_size (int, optional): The size of each chunk in bytes.
                                        Defaults to `File.DEFAULT_CHUNK_SIZE`.

        Yields:
            bytes: A chunk of data read from the file.

        Raises:
            AssertionError: If the file is closed.
        """
        assert self.file is not None, "File is closed"
        chunk_size = chunk_size or self.DEFAULT_CHUNK_SIZE

        try:
            # Attempt to seek to the beginning of the file.
            self.file.seek(0)
        except (AttributeError, OSError):
            # Ignore if seeking is not supported or fails.
            pass
        else:
            while True:
                data = self.file.read(chunk_size)
                if not data:  # End of file
                    break
                yield data

    def multiple_chunks(self, chunk_size: int | None = None) -> bool:
        """
        Indicates whether the file is likely to be read in multiple chunks.

        Args:
            chunk_size (int, optional): The chunk size to consider.
                                        Defaults to `File.DEFAULT_CHUNK_SIZE`.

        Returns:
            bool: True if the file size is greater than the chunk size, False otherwise.
        """
        if chunk_size is None:
            chunk_size = self.DEFAULT_CHUNK_SIZE
        return self.size > chunk_size

    def __enter__(self) -> File:
        """Allows `File` instances to be used in `with` statements."""
        assert self.file is not None, "File is closed"
        return self

    def __exit__(self, exc_type: Exception, exc_value: Any, tb: Any) -> None:
        """Ensures the file is closed when exiting a `with` statement."""
        self.close()

    def open(self, mode: str | None = None) -> File:
        """
        Opens the file with the specified mode. If the file is already open,
        it seeks to the beginning. If closed, it attempts to reopen it from storage.

        Args:
            mode (str, optional): The mode in which to open the file (e.g., "rb", "wb").
                                  If None, the existing mode of the file is used.

        Returns:
            File: The opened file instance.

        Raises:
            FileOperationError: If the file cannot be reopened (e.g., no name, or not found in storage).
        """
        if not self.closed:
            # If already open, just seek to the beginning.
            self.file.seek(0)
        elif self.name and self.storage.exists(self.name):
            # If closed but has a name and exists in storage, reopen from storage.
            self.file = self.storage.open(self.name, mode or self.mode)
        else:
            # Cannot reopen if no name or not found in storage.
            raise FileOperationError("The file cannot be reopened.")
        return self

    def readable(self) -> bool:
        """Returns True if the file is open and readable."""
        if self.closed:
            return False
        assert self.file is not None  # Type checker hint
        if hasattr(self.file, "readable"):
            return self.file.readable()
        return True  # Assume readable if no specific method

    def writable(self) -> bool:
        """Returns True if the file is open and writable."""
        if self.closed:
            return False
        assert self.file is not None  # Type checker hint
        if hasattr(self.file, "writable"):
            return self.file.writable()
        return "w" in getattr(self.file, "mode", "")  # Check 'w' in mode string

    def seekable(self) -> bool:
        """Returns True if the file is open and seekable."""
        if self.closed:
            return False
        assert self.file is not None  # Type checker hint
        if hasattr(self.file, "seekable"):
            return self.file.seekable()
        return False  # Assume not seekable if no specific method

    def seek(self, offset: int, whence: int = 0) -> int:
        """
        Seeks to a specific position in the file.

        Args:
            offset (int): The offset (number of bytes).
            whence (int): The reference point (0 for beginning, 1 for current, 2 for end).
                          Defaults to 0 (beginning).

        Returns:
            int: The new absolute position in the file.

        Raises:
            AssertionError: If the file is not seekable.
        """
        assert self.seekable()
        assert self.file is not None
        return self.file.seek(offset, whence)

    def tell(self) -> int:
        """
        Returns the current position of the file pointer.

        Returns:
            int: The current position.

        Raises:
            AssertionError: If the file is closed.
        """
        assert self.file is not None
        return self.file.tell()

    def read(self, amount: int | None = None) -> bytes:
        """
        Reads data from the file.

        Args:
            amount (int | None): The number of bytes to read. If None, reads all remaining data.

        Returns:
            bytes: The data read from the file.

        Raises:
            AttributeError: If unable to seek to the beginning of the file.
            AssertionError: If the file is closed.
        """
        assert self.file is not None
        return self.file.read(amount)

    def write(self, data: bytes) -> int:
        """
        Writes data to the file. Invalidates the cached size.

        Args:
            data (bytes): The bytes data to write.

        Returns:
            int: The number of bytes written.

        Raises:
            AssertionError: If the file is closed.
        """
        assert self.file is not None
        # Invalidate cached size as content has changed.
        self.__dict__.pop("size", None)
        return self.file.write(data)

    def close(self, keep_size: bool = False) -> None:
        """
        Closes the underlying file object and clears the `file` attribute.
        Optionally keeps the cached size.

        Args:
            keep_size (bool): If True, the cached `size` property is not invalidated.
                              Defaults to False.
        """
        if self.file is None:
            return
        self.file.close()
        self.file = None
        if not keep_size:
            # Invalidate cached size.
            self.__dict__.pop("size", None)


class ContentFile(File):
    """
    A specialized `File` class for handling file content that is entirely
    held in memory (e.g., raw bytes or strings). It uses `BytesIO` as its
    underlying file object.

    The `size` property is directly set at initialization as the length of the content.
    """

    file: BinaryIO  # Ensures that `file` is always a BinaryIO for ContentFile.

    def __init__(self, content: bytes, name: str = ""):
        """
        Initializes a ContentFile instance.

        Args:
            content (bytes): The raw bytes content of the file.
            name (str): The name (path) of the file. Defaults to "".
        """
        super().__init__(file=BytesIO(content), name=name)
        # Directly set size as it's known from the content.
        self.size = len(content)

    def __str__(self) -> str:
        """Returns a generic string representation for raw content files."""
        return "Raw content"

    def open(self, mode: str | Any = None) -> ContentFile:
        """
        For `ContentFile`, opening simply means seeking to the beginning of the
        in-memory buffer. The `mode` argument is ignored as it's always an in-memory stream.

        Args:
            mode (str | Any, optional): Ignored. Defaults to None.

        Returns:
            ContentFile: The instance itself, with its internal buffer reset to the beginning.
        """
        self.file.seek(0)
        return self

    def close(self, keep_size: bool = False) -> None:
        """
        Closes the ContentFile. Invalidate the cached size unless `keep_size` is True.
        Note: The underlying BytesIO is typically not 'closed' in a way that
        prevents further access, but its resources are freed.

        Args:
            keep_size (bool): If True, the cached `size` property is not invalidated.
                              Defaults to False.
        """
        if not keep_size:
            self.__dict__.pop("size", None)


class FieldFile(File):
    """
    A specialized `File` class designed to be used with database model fields.
    It tracks operations (save, delete) that need to be performed on the file
    when the model is saved and manages an "approved" status for file operations.
    """

    # Tracks the pending operation: "none", "save", "save_delete", "delete".
    operation: Literal["none", "save", "save_delete", "delete"] = "none"
    # Stores old storage, name, and approved status for rollback or conditional deletion.
    old: tuple[Storage, str, bool] | None = None
    instance: BaseModelType | None = None  # The model instance this file field belongs to.
    approved: bool  # Indicates if the file operation (e.g., save, delete) is approved.
    metadata: dict[str, Any]  # Stores additional metadata about the file.

    def __init__(
        self,
        field: BaseFieldType,
        content: BinaryIO | bytes | None | File = None,
        name: str = "",
        size: int | None = None,
        storage: Storage | str | None = None,
        generate_name_fn: Callable[[str, BinaryIO | File, bool], str] | None = None,
        metadata: dict[str, Any] | None = None,
        multi_process_safe: bool = True,
        approved: bool = True,
        # only usable with correct approval handling
        change_removes_approval: bool = False,
    ) -> None:
        """
        Initializes a FieldFile instance.

        Args:
            field (BaseFieldType): The database field associated with this file.
            content (BinaryIO | bytes | None | File): Initial file content.
            name (str): Initial file name.
            size (int | None): Pre-determined size of the file. If provided, `cached_property`
                               for size is bypassed.
            storage (Storage | str | None): The storage backend.
            generate_name_fn (Callable[[str, BinaryIO | File, bool], str] | None):
                A callable to generate a unique file name. Takes (original_name, file_content, direct_name_provided).
            metadata (dict[str, Any] | None): Additional metadata for the file.
            multi_process_safe (bool): If True, incorporates process ID into filename for multi-process safety.
            approved (bool): Initial approval status of the file. Operations on this file
                             might be restricted if not approved. Defaults to True.
            change_removes_approval (bool): If True, any change to the file (save/delete)
                                            will set `approved` to False. Defaults to False.
        """
        super().__init__(content, name=name, storage=storage)
        self.field = field
        self.generate_name_fn = generate_name_fn
        self.metadata = metadata or {}
        self.multi_process_safe = multi_process_safe
        self.change_removes_approval = change_removes_approval
        self.approved = approved
        if size is not None:
            # Set the size directly, bypassing the cached_property logic.
            self.size = size

    def to_file(self) -> File | None:
        """
        Converts the `FieldFile` into a regular `File` instance. This is useful
        for creating copies or when the file needs to be treated as a generic file.

        Returns:
            File | None: A new `File` instance if `self` is not empty, otherwise None.
        """
        if self:
            # Use `copy(self)` to get a shallow copy of the underlying file object,
            # then wrap it in a new `File` instance.
            return File(cast(BinaryIO, copy(self)), name=self.name, storage=self.storage)
        return None

    def _execute_operation(self, nodelete_old: bool) -> None:
        """
        Synchronously executes the pending file operation (`save`, `delete`).
        This method is designed to be called in a separate thread for async operations.

        Args:
            nodelete_old (bool): If True, prevents deletion of the old file during a 'save_delete' operation.
        """
        operation = self.operation
        self.operation = "none"  # Reset operation to prevent re-execution.

        if operation == "save" or operation == "save_delete":
            if self.file is None or not self.name:
                raise ValueError(
                    f"The '{self.field.name}' attribute has no file associated with it."
                )
            try:
                self.storage.save(self.file, self.name)
            finally:
                # Ensure the name is unreserved even if save fails.
                self.storage.unreserve_name(self.name)

            if (
                not nodelete_old
                and operation == "save_delete"
                and self.old is not None  # Check if there's old file info
                and self.old[1]  # Check if old name is not empty
                and self.old[1] != self.name  # Only delete if name has changed
            ):
                self.old[0].delete(self.old[1])  # Delete the old file from its storage.
        elif operation == "delete":
            if getattr(self, "file", None):
                self.close()  # Close the associated file object.
            # Delete the old file if it exists and deletion is not suppressed.
            if not nodelete_old and self.old is not None and self.old[1]:
                self.old[0].delete(self.old[1])
        # else: For "none" operation or metadata update, no file system action.
        self.old = None  # Clear old file information after operation.

    async def execute_operation(self, nodelete_old: bool = False) -> None:
        """
        Asynchronously executes the pending file operation.
        It wraps the synchronous `_execute_operation` in `asyncio.to_thread`
        to prevent blocking the event loop.

        Args:
            nodelete_old (bool): If True, prevents deletion of the old file during a 'save_delete' operation.
        """
        await asyncio.to_thread(self._execute_operation, nodelete_old=nodelete_old)

    def save(
        self,
        content: BinaryIO | bytes | None | File | FileStruct,
        *,
        name: str = "",
        delete_old: bool = True,
        multi_process_safe: bool | None = None,
        approved: bool | None = None,
        storage: Storage | None = None,
        overwrite: bool = False,
    ) -> None:
        """
        Prepares the file for saving to storage. This method handles content type
        conversion, filename generation, and marks the appropriate operation to be
        executed later (e.g., when the model is saved).

        Args:
            content (BinaryIO | bytes | None | File | FileStruct): The new file content.
                                                                    If None, the file is marked for deletion.
            name (str): The desired name for the file. If empty, attempts to infer.
            delete_old (bool): If True, the old file (if any) will be deleted upon saving the new one.
            multi_process_safe (bool | None): Overrides instance's `multi_process_safe`.
                                              If True, process ID is added to filename.
                                              Defaults to `False` if `overwrite` is `True`,
                                              else `self.multi_process_safe`.
            approved (bool | None): Overrides the file's approval status.
            storage (Storage | None): Overrides the default storage for this save operation.
            overwrite (bool): If True, allows overwriting an existing file with the same name.
                              If False, an alternative name will be generated.
        """
        if content is None:
            self.delete()  # If content is None, mark for deletion.
            return

        direct_name = True  # Flag to indicate if name was directly provided
        if isinstance(content, FileStruct):
            if not name:
                name = content.name
                direct_name = False  # Name was from FileStruct, not direct init
            assert isinstance(name, str)
            content = content.content  # Extract actual bytes content

        # Determine multi_process_safe behavior.
        if multi_process_safe is None:
            multi_process_safe = False if overwrite else self.multi_process_safe

        # If name is still empty, try to get it from the content object.
        if not name:
            direct_name = False
            name = getattr(content, "name", "")

        # Convert content to a standard File object if it's not already.
        if isinstance(content, File):
            content = content.open("rb").file
        elif isinstance(content, bytes):
            content = BytesIO(content)

        # Generate filename using the provided callable, if any.
        if self.generate_name_fn is not None:
            name = self.generate_name_fn(name, content, direct_name)

        if not name:
            raise ValueError("No name found for the file.")

        # Determine the storage to use for this save operation.
        if storage is None:
            storage = self.storage

        # Get an available name from the storage, handling conflicts and max_length.
        name = storage.get_available_name(
            name,
            max_length=getattr(self.field, "max_length", None),  # Use max_length from field
            overwrite=overwrite,
            multi_process_safe=multi_process_safe,
        )

        # Close any existing file object associated with this FieldFile.
        if getattr(self, "file", None):
            self.close()

        # Update the FieldFile's state to reflect the new file.
        self.file = content
        self.old = (
            self.storage,
            self.name,
            self.approved,
        )  # Store old state for rollback/deletion
        self.storage = storage  # Update storage if changed
        self.name = name  # Set the new, available name
        self.operation = "save_delete" if delete_old else "save"  # Mark pending operation

        # Update approval status.
        if approved is not None:
            self.approved = approved
        elif self.change_removes_approval:
            self.approved = False  # Change removes approval if configured.

    def set_approved(self, approved: bool) -> None:
        """
        Sets the approval status of the file and stores the old state.

        Args:
            approved (bool): The new approval status.
        """
        self.old = (self.storage, self.name, self.approved)  # Store old state.
        self.approved = approved

    def reset(self) -> None:
        """
        Resets any staged file operation, effectively undoing a `save` or `delete`
        call if the operation hasn't been executed yet. This involves:
        - Closing newly assigned file content.
        - Unreserving any newly reserved names.
        - Restoring the file's name and approval status to its original state.
        """
        if self.operation == "save" or self.operation == "save_delete":
            # If there was a pending save, close the new file and unreserve its name.
            if getattr(self, "file", None):
                self.close()
            self.storage.unreserve_name(self.name)
        if self.old is not None:
            # Restore previous state if an 'old' state was stored.
            self.storage, self.name, self.approved = self.old
            self.old = None  # Clear old state.
        self.operation = "none"  # Reset operation to none.

    def delete(self, *, approved: bool | None = None, instant: bool = False) -> None:
        """
        Marks the file associated with this object for deletion from storage,
        or performs instant deletion.

        Args:
            approved (bool | None): Overrides the file's approval status for this deletion.
            instant (bool): If True, the file is deleted immediately from storage.
                            If False, the deletion is staged to occur when the model is saved.

        Raises:
            FileOperationError: If the field is not nullable and `instant` is False (cannot delete without replacing).
        """
        if not self:
            return  # Nothing to delete if file is empty.

        if not self.field.null and not instant:
            # If the field is not nullable, you cannot simply delete; it must be replaced.
            # This check is skipped for instant deletion as it implies the model is being
            # modified or deleted itself.
            raise FileOperationError("Cannot delete file (only replacing is possible)")

        self.reset()  # Reset any pending operations first.

        if instant:
            # Perform instant deletion:
            if getattr(self, "file", None):
                self.close()  # Close the associated file object.
            self.storage.delete(self.name)  # Delete from storage.
            # If the field allows null, clear the name.
            if self.field.null:
                self.name = ""
            # Update approval status.
            if approved is not None:
                self.approved = approved
            elif self.change_removes_approval:
                self.approved = False
            return

        # Stage for deferred deletion:
        self.old = (self.storage, self.name, self.approved)  # Store old state.
        self.name = ""  # Clear the name to indicate deletion.
        self.operation = "delete"  # Mark pending operation.
        # Update approval status.
        if approved is not None:
            self.approved = approved
        elif self.change_removes_approval:
            self.approved = False

    def close(self, keep_size: bool = False) -> None:
        if self.operation == "none":
            super().close(keep_size=keep_size)


class ImageFieldFile(FieldFile):
    """
    A specialized `FieldFile` for image files. Provides an `open_image` method
    to load the image using Pillow, optionally validating against allowed formats.
    """

    def open_image(self) -> ImageFile:
        """
        Opens the image file using Pillow's `Image.open()`.
        Applies format restrictions based on `field.image_formats` and `field.approved_image_formats`
        if the file is approved.

        Returns:
            ImageFile: A Pillow `ImageFile` object.

        Raises:
            ImportError: If Pillow (PIL) is not installed.
            FileNotFoundError: If the image file does not exist.
            PIL.UnidentifiedImageError: If the file content is not a valid image format.
        """
        from PIL import Image  # pyright: ignore[reportMissingImports]

        allowed_formats: Sequence[str] | None = getattr(self.field, "image_formats", ())
        if self.approved and allowed_formats is not None:
            # If approved, consider both general allowed formats and approved-specific formats.
            approved_image_formats: Sequence[str] | None = getattr(
                self.field, "approved_image_formats", ()
            )
            if approved_image_formats is None:
                # If approved_image_formats is None, allow all formats if allowed_formats was not None.
                allowed_formats = None
            else:
                # Combine general and approved-specific formats.
                allowed_formats = (*allowed_formats, *approved_image_formats)

        # Open the underlying binary file stream and pass it to Pillow's Image.open.
        return Image.open(self.open("rb"), formats=allowed_formats)  # type: ignore
