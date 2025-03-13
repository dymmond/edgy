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

# for silencing warning
CHECK_DB_CONNECTION_SILENCED = ContextVar("CHECK_DB_CONNECTION_SILENCED", default=False)


def check_db_connection(db: "Database", stacklevel: int = 3) -> None:
    if not db.is_connected:
        # with force_rollback the effects are even worse, so fail
        if db.force_rollback:
            raise RuntimeError("db is not connected.")
        if not CHECK_DB_CONNECTION_SILENCED.get():
            # db engine will be created and destroyed afterwards
            warnings.warn(
                "Database not connected. Executing operation is inperformant.",
                DatabaseNotConnectedWarning,
                stacklevel=stacklevel,
            )


@lru_cache(512, typed=False)
def _hash_tablekey(tablekey: str, prefix: str) -> str:
    return f"_join{hash_to_identifier(f'{tablekey}_{prefix}')}"


def hash_tablekey(*, tablekey: str, prefix: str) -> str:
    """
    For temporary aliases like joins.
    Columns can be extracted from joins by adding to the hash `_<column name>`.
    """
    if not prefix:
        return tablekey
    return _hash_tablekey(tablekey, prefix)


def hash_names(
    field_or_col_names: Iterable[str], *, inner_prefix: str, outer_prefix: str = ""
) -> str:
    hashed = hash_to_identifier(f"{inner_prefix}_{','.join(sorted(field_or_col_names))}")
    if outer_prefix:
        hashed = f"{outer_prefix}{hashed}"
    return hashed


def force_fields_nullable_as_list_string(apostroph: str = '"') -> str:
    items = FORCE_FIELDS_NULLABLE.get()
    if not all(apostroph not in item[0] and apostroph not in item[1] for item in items):
        raise RuntimeError(f"{apostroph} was found in items")
    joined = ", ".join(
        f"({apostroph}{item[0]}{apostroph}, {apostroph}{item[1]}{apostroph})" for item in items
    )
    return f"[{joined}]"
