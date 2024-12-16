import warnings
from contextvars import ContextVar
from functools import lru_cache
from typing import TYPE_CHECKING

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
    return f'_join{hash_to_identifier(f"{tablekey}_{prefix}")}'


def hash_tablekey(*, tablekey: str, prefix: str) -> str:
    """
    For temporary aliases like joins.
    Columns can be extracted from joins by adding to the hash `_<column name>`.
    """
    if not prefix:
        return tablekey
    return _hash_tablekey(tablekey, prefix)
