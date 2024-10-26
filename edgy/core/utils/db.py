import warnings
from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from edgy.core.connection.database import Database


def check_db_connection(db: "Database") -> None:
    if not db.is_connected:
        # with force_rollback the effects are even worse, so fail
        if db.force_rollback:
            raise RuntimeError("db is not connected.")
        # db engine will be created and destroyed afterwards
        warnings.warn(
            "Database not connected. Executing operation is inperformant.",
            UserWarning,
            stacklevel=2,
        )


@lru_cache(512, typed=False)
def _hash_tablekey(tablekey: str, prefix: str) -> str:
    tablehash_hex = hex(hash(f"{tablekey}_{prefix}"))
    tablehash = f"n{tablehash_hex[3:]}" if tablehash_hex[0] == "-" else tablehash_hex[2:]

    return f"_join_{tablehash}"


def hash_tablekey(*, tablekey: str, prefix: str) -> str:
    """Only for joins. Not a stable hash."""
    if not prefix:
        return tablekey
    return _hash_tablekey(tablekey, prefix)
