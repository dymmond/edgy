import os
import sys
from functools import cached_property
from typing import Any, Generator, Union

from edgy.core.files.mixins import FileProxyMixin

if sys.version_info >= (3, 10):  # pragma: no cover
    from typing import ParamSpec
else:  # pragma: no cover
    from typing_extensions import ParamSpec


P = ParamSpec("P")


class File(FileProxyMixin):
    DEFAULT_CHUNK_SIZE = 64 * 2**10

    def __init__(self, file: Any, name: Union[str, None] = None) -> None:
        self._file = file

        if name is None:
            name = getattr(file, "name", None)

        self._name = name

        if hasattr(file, "mode"):
            self.mode = file.mode

    def __str__(self) -> str:
        return self._name or ""

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self or 'None'}>"

    def __bool__(self) -> bool:
        return bool(self._name)

    def __len__(self) -> int:
        return self.size

    @cached_property
    def size(self) -> int:
        """
        Return the size of the file.

        Returns:
            int: The size of the file in bytes.

        Raises:
            AttributeError: If unable to determine the file's size.
        """
        if hasattr(self._file, "size"):
            return self._file.size

        if hasattr(self._file, "name"):
            try:
                return os.path.getsize(self._file.name)
            except (OSError, TypeError):
                ...

        if hasattr(self._file, "seek"):
            pos = self._file.tell()
            try:
                self._file.seek(0, os.SEEK_END)
                size = self._file.tell()
            finally:
                self._file.seek(pos)
            return size

        raise AttributeError("Unable to determine the file's size.")

    def chunks(self, chunk_size: Union[int, None] = None):
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
        chunk_size = chunk_size or self.DEFAULT_CHUNK_SIZE

        try:
            self.seek(0)
        except (AttributeError, OSError):
            ...
        else:
            while True:
                data = self.read(chunk_size)
                if not data:
                    break
                yield data

    def multiple_chunks(self, chunk_size: Union[int, None] = None):
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

    def __iter__(self) -> Generator:
        """
        Iterate over this file-like object by newlines.

        Yields:
            bytes: Each line from the file.
        """
        buffer_ = None

        for chunk in self.chunks():
            lines = chunk.splitlines(True)
            if buffer_:
                if endswith_cr(buffer_) and not equals_lf(lines[0]):
                    yield buffer_
                else:
                    lines[0] = buffer_ + lines[0]
                buffer_ = None

            for line in lines:
                if endswith_lf(line):
                    yield line
                else:
                    buffer_ = line

        if buffer_ is not None:
            yield buffer_

    def __enter__(self) -> "File":
        return self

    def __exit__(self, exc_type: Exception, exc_value: Any, tb: Any) -> None:
        self.close()

    def open(self, mode: Union[str, None] = None, *args: P.args, **kwargs: P.kwargs) -> "File":
        """
        Open the file with the specified mode.

        Args:
            mode (str, optional): The mode in which to open the file. If not provided, uses the existing mode.
            *args: Positional arguments to be passed to the `open` function.
            **kwargs: Keyword arguments to be passed to the `open` function.

        Returns:
            FileProxyMixin: The opened file.

        Raises:
            ValueError: If the file cannot be reopened.
        """
        if not self.closed:
            self.seek(0)
        elif self._name and os.path.exists(self._name):
            self.file = open(self._name, mode or self.mode, *args, **kwargs)
        else:
            raise ValueError("The file cannot be reopened.")

        return self

    def close(self) -> None:
        self.file.close()


def endswith_cr(line: str) -> str:
    return line.endswith("\r" if isinstance(line, str) else b"\r")


def endswith_lf(line: str) -> str:
    return line.endswith("\n" if isinstance(line, str) else b"\n")


def equals_lf(line: str) -> str:
    return line == ("\n" if isinstance(line, str) else b"\n")
