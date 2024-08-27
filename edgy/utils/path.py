from os.path import abspath, dirname, join, normcase, sep
from typing import Any

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
