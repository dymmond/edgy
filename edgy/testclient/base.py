import os
from typing import TYPE_CHECKING

from databasez.testclient import DatabaseTestClient as _DatabaseTestClient

if TYPE_CHECKING:
    pass

default_test_prefix: str = "test_"
# for allowing empty
if "EDGY_TESTCLIENT_TEST_PREFIX" in os.environ:
    default_test_prefix = os.environ["EDGY_TESTCLIENT_TEST_PREFIX"]


class DatabaseTestClient(_DatabaseTestClient):
    """
    Adaption of DatabaseTestClient for edgy.

    Note: the default of lazy_setup is True here. This enables the simple Registry syntax.
    Note: the default of full_isolation is True here.

    """

    testclient_default_test_prefix = default_test_prefix

    testclient_default_lazy_setup: bool = (
        os.environ.get("EDGY_TESTCLIENT_LAZY_SETUP", "true") or ""
    ).lower() == "true"
    testclient_default_force_rollback: bool = (
        os.environ.get("EDGY_TESTCLIENT_FORCE_ROLLBACK") or ""
    ).lower() == "true"
    testclient_default_use_existing: bool = (
        os.environ.get("EDGY_TESTCLIENT_USE_EXISTING") or ""
    ).lower() == "true"
    testclient_default_drop_database: bool = (
        os.environ.get("EDGY_TESTCLIENT_DROP_DATABASE") or ""
    ).lower() == "true"
    testclient_default_full_isolation: bool = (
        os.environ.get("EDGY_TESTCLIENT_FULL_ISOLATION", "true") or ""
    ).lower() == "true"
