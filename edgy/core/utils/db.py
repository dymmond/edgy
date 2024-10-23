import base64
import hashlib
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
    tablehash = (
        base64.urlsafe_b64encode(hashlib.new("md5", f"{tablekey}_{prefix}".encode()).digest())
        .decode()
        .rstrip("=")
    )

    return f"_join_{tablehash}"


def hash_tablekey(*, tablekey: str, prefix: str) -> str:
    if not prefix:
        return tablekey
    return _hash_tablekey(tablekey, prefix)
