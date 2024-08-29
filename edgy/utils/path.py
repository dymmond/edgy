import os
import pathlib
import re
import secrets
import string
from os.path import abspath, dirname, join, normcase, sep
from typing import Any, Optional
from urllib.parse import quote

from edgy.exceptions import SuspiciousFileOperation


def safe_join(base: str, *paths: Any) -> str:
    final_path = _get_final_path(base, *paths)
    base_path = abspath(base)
    _validate_final_path(final_path, base_path)
    return final_path


def _get_final_path(base: str, *paths: Any) -> str:
    """
    Get the final path by joining base and other paths.

    Args:
        base (str): The base path.
        paths (str): Additional paths to join with the base path.

    Returns:
        str: The final joined path.
    """
    return abspath(join(base, *paths))


def _validate_final_path(final_path: str, base_path: str) -> None:
    """
    Validate the final path against the base path.

    Args:
        final_path (str): The final joined path.
        base_path (str): The base path.

    Raises:
        SuspiciousFileOperation: If the final path is not located inside the base path component.
    """
    if (
        not normcase(final_path).startswith(normcase(base_path + sep))
        and normcase(final_path) != normcase(base_path)
        and dirname(normcase(base_path)) != normcase(base_path)
    ):
        raise SuspiciousFileOperation(
            f"The joined path ({final_path}) is located outside of the base path "
            f"component ({base_path})"
        )


def get_valid_filename(name: str) -> str:
    """
    Cleans and validates a string to be used as a filename.

    Args:
        name (str): The string to be cleaned.

    Raises:
        SuspiciousFileOperation: If the resulting filename is empty or consists of '.', or '..'.

    Returns:
        str: The cleaned and validated filename.
    """
    # Strip leading and trailing whitespaces, and replace inner whitespaces with underscores
    cleaned_name = str(name).strip().replace(" ", "_")

    # Remove any characters that are not letters, numbers, hyphens, underscores, or dots
    cleaned_name = re.sub(r"(?u)[^-\w.]", "", cleaned_name)

    # Check if the resulting filename is empty or consists of '.', or '..'
    if cleaned_name in {"", ".", ".."}:
        raise SuspiciousFileOperation(f"Could not derive file name from '{name}'")

    return cleaned_name


def get_random_string(length: int = 10) -> str:
    """
    Generates a random string of specified length.

    Args:
        length (int, optional): The length of the random string. Defaults to 10.

    Returns:
        str: The generated random string.
    """
    letters = string.ascii_lowercase
    random_string = "".join(secrets.choice(letters) for _ in range(length))
    return random_string


def validate_file_name(name: str, allow_relative_path: bool = False) -> str:
    """
    Validate a file name to ensure it is safe and does not contain path traversal attempts.

    Args:
        name (str): The file name to be validated.
        allow_relative_path (bool, optional): Whether to allow relative paths. Defaults to False.

    Raises:
        SuspiciousFileOperation: If the file name is potentially dangerous or contains path traversal attempts.

    Returns:
        str: The validated file name.
    """
    base_name = os.path.basename(name)
    if base_name in {"", ".", ".."}:
        raise SuspiciousFileOperation(f"Could not derive file name from '{name}'")

    if allow_relative_path:
        path = pathlib.PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts:
            raise SuspiciousFileOperation(f"Detected path traversal attempt in '{name}'")
    elif name != base_name:
        raise SuspiciousFileOperation(f"File name '{name}' includes path elements")

    return name


def filepath_to_uri(path: Optional[str]) -> str:
    """
    Convert a file system path to a URI portion suitable for inclusion in a URL.

    Encode certain characters that would normally be recognized as special characters
    for URIs. Do not encode the ' character, as it is a valid character
    within URIs. See the encodeURIComponent() JavaScript function for details.

    Args:
        path (str): The file system path to convert.

    Returns:
        str: The URI portion suitable for inclusion in a URL.
    """
    if not path:
        return ""
    return quote(str(path).replace("\\", "/"), safe="/~!*()'")
