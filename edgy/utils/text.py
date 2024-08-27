import os
import pathlib
import random
import re
import string

from edgy.exceptions import SuspiciousFileOperation


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
    random_string = "".join(random.choice(letters) for _ in range(length))
    return random_string


def validate_file_name(name, allow_relative_path: bool = False):
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
