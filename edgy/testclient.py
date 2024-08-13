import os
import typing
from typing import TYPE_CHECKING, Any

from databasez.testclient import DatabaseTestClient as _DatabaseTestClient

if TYPE_CHECKING:
    import sqlalchemy
    from databasez import Database, DatabaseURL

# TODO: move this to the settings
default_test_prefix: str = "test_"
# for allowing empty
if "EDGY_TESTCLIENT_TEST_PREFIX" in os.environ:
    default_test_prefix = os.environ["EDGY_TESTCLIENT_TEST_PREFIX"]

default_use_existing: bool = (
    os.environ.get("EDGY_TESTCLIENT_USE_EXISTING") or ""
).lower() == "true"
default_drop_database: bool = (
    os.environ.get("EDGY_TESTCLIENT_DROP_DATABASE") or ""
).lower() == "true"


class DatabaseTestClient(_DatabaseTestClient):
    """
    Adaption of DatabaseTestClient for edgy.

    Note: the default of lazy_setup is True here. This enables the simple Registry syntax.
    """

    testclient_lazy_setup: bool = (
        os.environ.get("EDGY_TESTCLIENT_LAZY_SETUP", "true") or ""
    ).lower() == "true"
    testclient_force_rollback: bool = (
        os.environ.get("EDGY_TESTCLIENT_FORCE_ROLLBACK") or ""
    ).lower() == "true"

    # TODO: replace by testclient default overwrites
    def __init__(
        self,
        url: typing.Union[str, "DatabaseURL", "sqlalchemy.URL", "Database"],
        *,
        use_existing: bool = default_use_existing,
        drop_database: bool = default_drop_database,
        test_prefix: str = default_test_prefix,
        **options: Any,
    ):
        super().__init__(
            url,
            use_existing=use_existing,
            drop_database=drop_database,
            test_prefix=test_prefix,
            **options,
        )
