from __future__ import annotations

import contextlib
import os
from shutil import copymode, copystat

from edgy.core.files import locks

__all__ = ["file_move_safe"]


def _samefile(src: str, dst: str) -> bool:
    """
    Checks if two file paths refer to the same underlying file.
    This is a cross-platform helper that attempts to use `os.path.samefile`
    for robustness, falling back to a normalized path comparison if not available
    or if `os.path.samefile` raises an OSError.

    Args:
        src (str): The path to the source file.
        dst (str): The path to the destination file.

    Returns:
        bool: True if both paths refer to the same file, False otherwise.
    """
    if hasattr(os.path, "samefile"):
        try:
            # Use os.path.samefile for robust comparison on systems that support it.
            return os.path.samefile(src, dst)
        except OSError:
            # Fallback if os.path.samefile encounters an OS-level error (e.g., file not found).
            return False
    # Fallback for systems without os.path.samefile or if it fails:
    # Compare normalized absolute paths, ignoring case on case-insensitive file systems.
    return os.path.normcase(os.path.abspath(src)) == os.path.normcase(os.path.abspath(dst))


def file_move_safe(
    old_file_name: str,
    new_file_name: str,
    chunk_size: int = 1024 * 64,
    allow_overwrite: bool = False,
) -> None:
    """
    Moves a file from `old_file_name` to `new_file_name` in a safe and robust manner.
    It first attempts to use `os.rename` for an atomic move (which works only within
    the same filesystem). If `os.rename` fails (e.g., across filesystems), it falls
    back to a manual stream-based copy followed by deletion of the original file.

    It includes checks for existing destination files and handles file permissions.

    Args:
        old_file_name (str): The path to the file to be moved.
        new_file_name (str): The path to the destination location for the file.
        chunk_size (int, optional): The size of data chunks (in bytes) to read and write
                                    during the manual streaming process. Defaults to 64 KB.
        allow_overwrite (bool, optional): If True, an existing file at `new_file_name`
                                          will be overwritten. If False, and the destination
                                          file exists, a `FileExistsError` is raised.
                                          Defaults to False.

    Raises:
        FileExistsError: If the destination file exists and `allow_overwrite` is False.
        PermissionError: If there are insufficient permissions to perform file operations.
    """
    # If source and destination are the same file, no action is needed.
    if _samefile(old_file_name, new_file_name):
        return

    # Check for overwrite permission if the destination file already exists.
    if not allow_overwrite and os.access(new_file_name, os.F_OK):
        raise FileExistsError(
            f"Destination file {new_file_name} exists and allow_overwrite is False."
        )

    try:
        # Attempt to perform an atomic rename. This is fast and safe but fails
        # if source and destination are on different filesystems.
        os.rename(old_file_name, new_file_name)
        return  # If successful, the function completes here.
    except OSError:
        # If os.rename fails (e.g., cross-device link), fall through to manual copy.
        pass

    # Manual streaming copy if os.rename fails.
    # Open the old file for reading in binary mode.
    # Open the new file for writing, creating it exclusively (if not allowing overwrite)
    # and in binary mode.
    with (
        open(old_file_name, "rb") as old_file,
        os.open(
            new_file_name,
            (
                os.O_WRONLY  # Write-only
                | os.O_CREAT  # Create if not exists
                | getattr(os, "O_BINARY", 0)  # Binary mode (Windows specific)
                | (os.O_EXCL if not allow_overwrite else 0)  # Exclusive creation (if no overwrite)
            ),
        ) as fd,
    ):
        # Acquire an exclusive lock on the new file descriptor to prevent other processes
        # from writing to it concurrently during the copy operation.
        locks.lock(fd, locks.LOCK_EX)
        while True:
            # Read data in chunks from the old file.
            current_chunk = old_file.read(chunk_size)
            if not current_chunk:
                # Break loop if end of file is reached.
                break
            # Write the chunk to the new file using the file descriptor.
            os.write(fd, current_chunk)
        # Release the lock after writing is complete.
        locks.unlock(fd)

    try:
        # Attempt to copy file metadata (permissions, timestamps) from old to new.
        copystat(old_file_name, new_file_name)
    except PermissionError:
        # If copying all stats fails due to permission, try to copy only mode (permissions).
        with contextlib.suppress(PermissionError):
            copymode(old_file_name, new_file_name)

    try:
        # Finally, remove the original file.
        os.remove(old_file_name)
    except PermissionError as e:
        # On Windows, error 32 (ERROR_SHARING_VIOLATION) means the file is in use.
        # If it's not this specific error, re-raise the PermissionError.
        if getattr(e, "winerror", 0) != 32:
            raise
