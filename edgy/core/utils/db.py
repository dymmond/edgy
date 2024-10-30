import warnings
from base64 import b32encode
from functools import lru_cache
from hashlib import blake2b
from typing import TYPE_CHECKING

from edgy.exceptions import DatabaseNotConnectedWarning

if TYPE_CHECKING:
    from edgy.core.connection.database import Database


def check_db_connection(db: "Database", stacklevel: int = 3) -> None:
    if not db.is_connected:
        # with force_rollback the effects are even worse, so fail
        if db.force_rollback:
            raise RuntimeError("db is not connected.")
        # db engine will be created and destroyed afterwards
        warnings.warn(
            "Database not connected. Executing operation is inperformant.",
            DatabaseNotConnectedWarning,
            stacklevel=stacklevel,
        )


@lru_cache(512, typed=False)
def _hash_tablekey(tablekey: str, prefix: str) -> str:
    tablehash = (
        b32encode(blake2b(f"{tablekey}_{prefix}".encode(), digest_size=16).digest())
        .decode()
        .rstrip("=")
    )

    return f"_join_{tablehash}"


def hash_tablekey(*, tablekey: str, prefix: str) -> str:
    """
    For temporary aliases like joins.
    Columns can be extracted from joins by adding to the hash `_<column name>`.
    """
    if not prefix:
        return tablekey
    return _hash_tablekey(tablekey, prefix)
