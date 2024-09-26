import contextlib
import os
from shutil import copymode, copystat

from edgy.core.files import locks

__all__ = ["file_move_safe"]


def _samefile(src: str, dst: str) -> bool:
    """
    Check if two file paths refer to the same file.

    Args:
        src (str): Source file path.
        dst (str): Destination file path.

    Returns:
        bool: True if both paths refer to the same file, False otherwise.
    """
    if hasattr(os.path, "samefile"):
        try:
            return os.path.samefile(src, dst)
        except OSError:
            return False
    return os.path.normcase(os.path.abspath(src)) == os.path.normcase(os.path.abspath(dst))


def file_move_safe(
    old_file_name: str,
    new_file_name: str,
    chunk_size: int = 1024 * 64,
    allow_overwrite: bool = False,
) -> None:
    """
    Move a file from one location to another in the safest way possible.

    First, try `os.rename`, which is simple but will break across filesystems.
    If that fails, stream manually from one file to another in pure Python.

    If the destination file exists and `allow_overwrite` is `False`, raise
    `FileExistsError`.

    Args:
        old_file_name (str): Path to the file to be moved.
        new_file_name (str): Path to the destination location.
        chunk_size (int, optional): Size of each chunk to read and write. Defaults to 64 KB.
        allow_overwrite (bool, optional): Whether to allow overwriting an existing file. Defaults to False.

    Raises:
        FileExistsError: If the destination file exists and allow_overwrite is False.
    """
    if _samefile(old_file_name, new_file_name):
        return

    if not allow_overwrite and os.access(new_file_name, os.F_OK):
        raise FileExistsError(
            f"Destination file {new_file_name} exists and allow_overwrite is False."
        )

    try:
        os.rename(old_file_name, new_file_name)
        return
    except OSError:
        pass

    with (
        open(old_file_name, "rb") as old_file,
        os.open(
            new_file_name,
            (
                os.O_WRONLY
                | os.O_CREAT
                | getattr(os, "O_BINARY", 0)
                | (os.O_EXCL if not allow_overwrite else 0)
            ),
        ) as fd,
    ):
        locks.lock(fd, locks.LOCK_EX)
        while True:
            current_chunk = old_file.read(chunk_size)
            if not current_chunk:
                break
            os.write(fd, current_chunk)
        locks.unlock(fd)

    try:
        copystat(old_file_name, new_file_name)
    except PermissionError:
        with contextlib.suppress(PermissionError):
            copymode(old_file_name, new_file_name)

    try:
        os.remove(old_file_name)
    except PermissionError as e:
        if getattr(e, "winerror", 0) != 32:
            raise
