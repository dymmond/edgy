from __future__ import annotations

import warnings
from collections.abc import Iterable
from contextvars import ContextVar
from functools import lru_cache
from typing import TYPE_CHECKING

from edgy.core.db.context_vars import FORCE_FIELDS_NULLABLE
from edgy.exceptions import DatabaseNotConnectedWarning
from edgy.utils.hashing import hash_to_identifier

if TYPE_CHECKING:
    from edgy.core.connection.database import Database

# Context variable to control silencing of database connection warnings.
CHECK_DB_CONNECTION_SILENCED = ContextVar("CHECK_DB_CONNECTION_SILENCED", default=False)


def check_db_connection(db: Database, stacklevel: int = 3) -> None:
    """
    Checks the connection status of a database instance and raises warnings or errors.

    If the database is not connected and `force_rollback` is enabled, a `RuntimeError`
    is raised as this scenario can lead to severe issues. Otherwise, if the database
    is not connected and warnings are not silenced, a `DatabaseNotConnectedWarning`
    is issued to inform about potential performance implications.

    Parameters:
        db (Database): The database instance to check.
        stacklevel (int): The stack level for the warning, indicating where the warning
                          was issued. Defaults to 3.

    Raises:
        RuntimeError: If the database is not connected and `db.force_rollback` is True.
        DatabaseNotConnectedWarning: If the database is not connected and warnings
                                     are not silenced via `CHECK_DB_CONNECTION_SILENCED`.
    """
    if not db.is_connected:
        # If force_rollback is enabled, a disconnected database is critical.
        if db.force_rollback:
            raise RuntimeError("db is not connected.")
        # Check if warnings for disconnected database should be silenced.
        if not CHECK_DB_CONNECTION_SILENCED.get():
            # Issue a warning that the database is not connected, affecting performance.
            warnings.warn(
                "Database not connected. Executing operation is inperformant.",
                DatabaseNotConnectedWarning,
                stacklevel=stacklevel,
            )


@lru_cache(512, typed=False)
def _hash_tablekey(tablekey: str, prefix: str) -> str:
    """
    Generates a hashed identifier for a table key with a given prefix using LRU cache.

    This internal helper function is optimized with `lru_cache` to store up to 512
    previously computed hashes, improving performance for frequently requested
    table key-prefix combinations. It prepends "_join" to the hash.

    Parameters:
        tablekey (str): The primary key or identifier of the table.
        prefix (str): A prefix to incorporate into the hash, typically for uniqueness.

    Returns:
        str: A unique hashed string identifier prefixed with "_join".
    """
    return f"_join{hash_to_identifier(f'{tablekey}_{prefix}')}"


def hash_tablekey(*, tablekey: str, prefix: str) -> str:
    """
    Generates a hashed identifier for temporary aliases, such as those used in SQL joins.

    This function is primarily used to create unique identifiers for temporary tables
    or aliases in database operations, particularly for joins. It allows for
    disambiguation of columns by extending the hash with column names.

    Parameters:
        tablekey (str): The base key for the table, often its name or a unique identifier.
        prefix (str): A prefix to add to the hash, useful for creating distinct
                      identifiers for different join operations or temporary tables.

    Returns:
        str: A unique hashed string identifier for the table key with the given prefix.
             If the prefix is empty, the original tablekey is returned.
    """
    if not prefix:
        return tablekey
    # Delegate to the cached internal function for hash generation.
    return _hash_tablekey(tablekey, prefix)


def hash_names(
    field_or_col_names: Iterable[str], *, inner_prefix: str, outer_prefix: str = ""
) -> str:
    """
    Generates a unique hash from a collection of field or column names, with optional prefixes.

    This function takes an iterable of string names (e.g., database column names or
    model field names), sorts them for consistency, and then generates a
    deterministic hash. It supports an `inner_prefix` applied before hashing the
    names and an optional `outer_prefix` applied to the final hash. This is useful
    for creating unique identifiers for groups of fields or columns, for example,
    in composite keys or unique constraints.

    Parameters:
        field_or_col_names (Iterable[str]): An iterable of string names (e.g., column names).
        inner_prefix (str): A prefix to include in the hash calculation, applied
                            before hashing the sorted names.
        outer_prefix (str): An optional prefix to prepend to the final hashed string.
                            Defaults to an empty string.

    Returns:
        str: A unique hashed string representing the sorted collection of names,
             optionally prefixed.
    """
    # Hash the sorted, joined field/column names with the inner prefix.
    hashed = hash_to_identifier(f"{inner_prefix}_{','.join(sorted(field_or_col_names))}")
    # If an outer prefix is provided, prepend it to the generated hash.
    if outer_prefix:
        hashed = f"{outer_prefix}{hashed}"
    return hashed


def force_fields_nullable_as_list_string(apostroph: str = '"') -> str:
    """
    Retrieves and formats the globally forced nullable fields as a string representation of a list.

    This function accesses a `ContextVar` that holds a collection of fields
    that are explicitly forced to be nullable. It formats these fields into
    a string that resembles a Python list of tuples, where each tuple contains
    two strings. It also validates that the specified `apostroph` character
    is not present within the field names to prevent formatting issues.

    Parameters:
        apostroph (str): The apostrophe character to use for quoting strings
                         within the generated list. Defaults to a double quote `"` .

    Returns:
        str: A string representation of a list of tuples, where each tuple
             represents a (schema, field) pair forced to be nullable.

    Raises:
        RuntimeError: If the specified `apostroph` character is found within
                      any of the field names, which could lead to malformed strings.
    """
    # Retrieve the list of items from the ContextVar.
    items = FORCE_FIELDS_NULLABLE.get()
    # Validate that the apostrophe character is not present in any item to prevent injection issues.
    if not all(apostroph not in item[0] and apostroph not in item[1] for item in items):
        raise RuntimeError(f"{apostroph} was found in items")
    # Join the items into a comma-separated string of formatted tuples.
    joined = ", ".join(
        f"({apostroph}{item[0]}{apostroph}, {apostroph}{item[1]}{apostroph})" for item in items
    )
    # Return the complete string representation of the list.
    return f"[{joined}]"
