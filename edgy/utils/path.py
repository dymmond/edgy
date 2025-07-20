from __future__ import annotations

import os
import pathlib
import re
import secrets
import string
from os.path import abspath, dirname, join, normcase, sep
from typing import Any
from urllib.parse import quote

from edgy.exceptions import SuspiciousFileOperation


def safe_join(base: str, *paths: Any) -> str:
    """
    Safely joins one or more path components to a base path.

    This function prevents directory traversal attacks by ensuring that the
    resulting path always remains within the specified base directory.

    Args:
        base (str): The base directory path.
        *paths (Any): One or more path components to join.

    Returns:
        str: The safely joined and normalized absolute path.

    Raises:
        SuspiciousFileOperation: If the joined path attempts to escape the base directory.
    """
    # Get the absolute and normalized final path by joining base and other paths.
    final_path = _get_final_path(base, *paths)
    # Get the absolute and normalized base path for comparison.
    base_path = abspath(base)
    # Validate that the final path does not escape the base path.
    _validate_final_path(final_path, base_path)
    return final_path


def _get_final_path(base: str, *paths: Any) -> str:
    """
    Helper function to get the absolute and joined path.

    Args:
        base (str): The base path.
        paths (str): Additional paths to join with the base path.

    Returns:
        str: The absolute and joined path.
    """
    return abspath(join(base, *paths))


def _validate_final_path(final_path: str, base_path: str) -> None:
    """
    Helper function to validate the final path against the base path.

    Ensures that `final_path` is either `base_path` itself or a sub-path
    within `base_path`.

    Args:
        final_path (str): The final joined path.
        base_path (str): The base path.

    Raises:
        SuspiciousFileOperation: If the final path is not located inside the base path.
    """
    # Normalize paths for platform-independent comparison.
    normalized_final_path = normcase(final_path)
    normalized_base_path = normcase(base_path)

    # Check if the final path starts with the base path followed by a separator.
    # This covers subdirectories.
    starts_with_base = normalized_final_path.startswith(normalized_base_path + sep)
    # Check if the final path is exactly the base path.
    is_base_path = normalized_final_path == normalized_base_path
    # Check if the base path itself is a directory (important for root directories).
    base_is_dir = dirname(normalized_base_path) != normalized_base_path

    # If the final path is not within the base path and the base path is a valid directory.
    if not starts_with_base and not is_base_path and base_is_dir:
        raise SuspiciousFileOperation(
            f"The joined path ({final_path}) is located outside of the base path "
            f"component ({base_path})"
        )


def get_valid_filename(name: str) -> str:
    """
    Cleans and validates a string to be used as a filename.

    This function removes unsafe characters, replaces spaces, and performs
    basic checks to prevent problematic filenames.

    Args:
        name (str): The string to be cleaned and validated.

    Returns:
        str: The cleaned and validated filename.

    Raises:
        SuspiciousFileOperation: If the resulting filename is empty or consists of
                                 '.', or '..', which are reserved or indicate directory traversal.
    """
    # Strip leading/trailing whitespaces and replace inner whitespaces with underscores.
    cleaned_name = str(name).strip().replace(" ", "_")

    # Remove any characters that are not letters, numbers, hyphens, underscores, or dots.
    # `(?u)` enables Unicode matching. `\w` includes letters, numbers, and underscore.
    cleaned_name = re.sub(r"(?u)[^-\w.]", "", cleaned_name)

    # Check for reserved or dangerous filenames.
    if cleaned_name in {"", ".", ".."}:
        raise SuspiciousFileOperation(f"Could not derive file name from '{name}'")

    return cleaned_name


def get_random_string(length: int = 10) -> str:
    """
    Generates a cryptographically strong pseudo-random string of specified length,
    consisting of lowercase ASCII letters.

    This uses `secrets` module for generating random strings suitable for
    security-sensitive contexts like tokens or temporary passwords, if needed,
    but defaults to lowercase ASCII for simplicity.

    Args:
        length (int, optional): The desired length of the random string. Defaults to 10.

    Returns:
        str: The generated random string.
    """
    letters = string.ascii_lowercase
    # Use secrets.choice for cryptographic randomness.
    random_string = "".join(secrets.choice(letters) for _ in range(length))
    return random_string


def validate_file_name(name: str, allow_relative_path: bool = False) -> str:
    """
    Validates a file name to ensure it is safe and does not contain path traversal attempts.

    This function checks for empty, reserved, or explicit path traversal sequences.
    It can optionally allow simple relative paths (e.g., "subdir/file.txt") but
    still prevents malicious attempts (e.g., "../../../secret.txt").

    Args:
        name (str): The file name string to be validated.
        allow_relative_path (bool, optional): If `True`, permits relative paths
                                               like "subdir/file.txt". If `False`,
                                               only a plain filename (no directory
                                               separators) is allowed. Defaults to `False`.

    Returns:
        str: The validated file name (the original `name` if valid).

    Raises:
        SuspiciousFileOperation: If the file name is empty, reserved, absolute,
                                 contains '..', or includes path elements when
                                 `allow_relative_path` is `False`.
    """
    # Extract the base name to check for reserved names.
    base_name = os.path.basename(name)
    if base_name in {"", ".", ".."}:
        raise SuspiciousFileOperation(f"Could not derive file name from '{name}'")

    if allow_relative_path:
        # Use pathlib.PurePosixPath for cross-platform path handling and checks.
        path = pathlib.PurePosixPath(name)
        # Prevent absolute paths or paths containing '..' for traversal.
        if path.is_absolute() or ".." in path.parts:
            raise SuspiciousFileOperation(f"Detected path traversal attempt in '{name}'")
    elif name != base_name:
        # If relative paths are not allowed, the name must be just a base filename.
        raise SuspiciousFileOperation(f"File name '{name}' includes path elements")

    return name


def filepath_to_uri(path: str | None) -> str:
    """
    Converts a file system path to a URI-encoded string suitable for inclusion in a URL.

    This function encodes characters that have special meaning in URIs (e.g., spaces, slashes)
    but specifically *does not* encode the single quote `'` character, as it's
    considered valid within URI paths in some contexts (similar to JavaScript's `encodeURIComponent`).
    Backslashes are converted to forward slashes for URL compatibility.

    Args:
        path (str | None): The file system path to convert. If `None`, an empty string is returned.

    Returns:
        str: The URI-encoded path string.

    Examples:
        ```python
        filepath_to_uri("/path/to/my file.txt")  # -> "/path/to/my%20file.txt"
        filepath_to_uri("C:\\Users\\file'name.doc") # -> "C:/Users/file'name.doc" (only \\ to /)
        ```
    """
    if not path:
        return ""
    # Replace backslashes with forward slashes for URL compatibility.
    # Then, use urllib.parse.quote to URL-encode the path.
    # The `safe` parameter specifies characters that should *not* be quoted.
    return quote(str(path).replace("\\", "/"), safe="/~!*()'")
