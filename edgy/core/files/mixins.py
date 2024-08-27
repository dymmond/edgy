import os
from functools import cached_property
from typing import Any


class FileProxyMixin:
    _file: Any

    @cached_property
    def size(self) -> int:
        if hasattr(self._file, "size"):
            return self._file.size
        if hasattr(self._file, "name"):
            try:
                return os.path.getsize(self.file.name)
            except (OSError, TypeError):
                pass
        if hasattr(self._file, "tell") and hasattr(self._file, "seek"):
            pos = self._file.tell()
            self._file.seek(0, os.SEEK_END)
            size = self._file.tell()
            self._file.seek(pos)
            return size
        raise AttributeError("Unable to determine the file's size.")

    def __len__(self) -> int:
        return self.size

    @property
    def closed(self) -> bool:
        """Return True if the file is closed."""
        return not self._file or self._file.closed

    def readable(self) -> bool:
        """Return True if the file is readable."""
        if self.closed:
            return False
        if hasattr(self._file, "readable"):
            return self._file.readable()
        return True

    def writable(self) -> bool:
        """Return True if the file is writable."""
        if self.closed:
            return False
        if hasattr(self._file, "writable"):
            return self._file.writable()
        return "w" in getattr(self._file, "mode", "")

    def seekable(self) -> bool:
        """Return True if the file is seekable."""
        if self.closed:
            return False
        if hasattr(self._file, "seekable"):
            return self._file.seekable()
        return True

    def __getattr__(self, name: str) -> Any:
        return getattr(self._file, name)


class StorageMixin:
    def value_or_setting(self, value: Any, setting: Any) -> Any:
        return setting if value is None else value
