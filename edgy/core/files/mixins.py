class FileProxyMixin:
    @property
    def encoding(self):
        """Return the file's encoding."""
        return self._file.encoding

    @property
    def fileno(self):
        """Return the file descriptor."""
        return self._file.fileno

    @property
    def flush(self):
        """Flush the file."""
        return self._file.flush

    @property
    def isatty(self):
        """Return True if the file is connected to a TTY device."""
        return self._file.isatty

    @property
    def newlines(self):
        """Return a line ending translation dictionary."""
        return self._file.newlines

    @property
    def read(self):
        """Read and return the entire contents of the file."""
        return self._file.read

    @property
    def readinto(self):
        """Read up to the next len(b) bytes into buffer b."""
        return self._file.readinto

    @property
    def readline(self):
        """Read and return a line from the file."""
        return self._file.readline

    @property
    def readlines(self):
        """Read and return a list of lines from the file."""
        return self._file.readlines

    @property
    def seek(self):
        """Change the file position to the given offset."""
        return self._file.seek

    @property
    def tell(self):
        """Return the current file position."""
        return self._file.tell

    @property
    def truncate(self):
        """Truncate the file to at most size bytes."""
        return self._file.truncate

    @property
    def write(self):
        """Write the string s to the file."""
        return self._file.write

    @property
    def writelines(self):
        """Write a sequence of strings to the file."""
        return self._file.writelines

    @property
    def closed(self):
        """Return True if the file is closed."""
        return not self._file or self._file.closed

    def readable(self):
        """Return True if the file is readable."""
        if self.closed:
            return False
        if hasattr(self._file, "readable"):
            return self._file.readable()
        return True

    def writable(self):
        """Return True if the file is writable."""
        if self.closed:
            return False
        if hasattr(self._file, "writable"):
            return self._file.writable()
        return "w" in getattr(self._file, "mode", "")

    def seekable(self):
        """Return True if the file is seekable."""
        if self.closed:
            return False
        if hasattr(self._file, "seekable"):
            return self._file.seekable()
        return True

    def __iter__(self):
        """Return an iterator object."""
        return iter(self._file)


class StorageMixin:

    def value_or_setting(self, value, setting):
        return setting if value is None else value
