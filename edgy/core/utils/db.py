import warnings
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
