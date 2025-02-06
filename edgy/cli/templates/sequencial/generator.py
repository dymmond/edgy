import os
import re
from typing import Union

MIGRATIONS_DIR = "migrations/versions"
FILENAME_PATTERN = re.compile(r"(\d{4})_(.*)\.py")


def get_next_migration_number() -> int:
    """
    Determines the next migration number by scanning the existing migration files in the MIGRATIONS_DIR.
    The function lists all files in the MIGRATIONS_DIR and extracts the migration numbers using the FILENAME_PATTERN.
    It then returns the next migration number, which is one greater than the highest existing migration number.
    If no migration files are found, it returns 1.
    Returns:
        int: The next migration number.
    """
    existing_files = os.listdir(MIGRATIONS_DIR)
    numbers = [
        int(FILENAME_PATTERN.match(f).group(1))
        for f in existing_files
        if FILENAME_PATTERN.match(f)
    ]
    return max(numbers, default=0) + 1


def get_sequencial_revision_number() -> str:
    """
    Generates a sequential revision number for migrations.
    This function retrieves the next migration number using the
    `get_next_migration_number` function and formats it as a
    zero-padded 4-digit string.
    Returns:
        str: The next migration number formatted as a 4-digit string.
    """

    next_number = get_next_migration_number()
    return f"{next_number:04d}"


def create_migration_filename(slug: Union[str, None] = None, with_extension: bool = False) -> str:
    """
    Generates a migration filename based on the next migration number and a given slug.
    Args:
        slug (str): The slug to be included in the filename.
        with_extension (bool, optional): If True, the filename will include an extension. Defaults to False.
    Returns:
        str: The generated migration filename.
    """
    next_number = get_next_migration_number()
    if slug is None:
        return f"{next_number:04d}_"

    return f"{next_number:04d}_{slug}" if with_extension else f"{next_number:04d}"


if __name__ == "__main__":
    slug = input("Enter a slug for the migration: ")
    filename = create_migration_filename(slug)
    print(f"New migration filename: {filename}")
