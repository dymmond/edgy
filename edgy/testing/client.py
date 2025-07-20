import os

from databasez.testclient import DatabaseTestClient as _DatabaseTestClient

# Determine the default test prefix for database names from environment variables.
# This allows users to customize how test databases are prefixed.
default_test_prefix: str = "test_"
# for allowing empty prefix
if "EDGY_TESTCLIENT_TEST_PREFIX" in os.environ:
    default_test_prefix = os.environ["EDGY_TESTCLIENT_TEST_PREFIX"]


class DatabaseTestClient(_DatabaseTestClient):
    """
    An adaptation of `databasez.testclient.DatabaseTestClient` specifically for Edgy.

    This class provides a testing client for Edgy applications, offering enhanced
    control over database setup, teardown, and transaction management during tests.
    It extends the base `DatabaseTestClient` from `databasez` by adjusting some
    default behaviors and integrating with Edgy's specific needs.

    Key adaptations include:
    * `lazy_setup` defaults to `True`: This enables a simpler `Registry` syntax,
        deferring database setup until explicitly needed, which can optimize test
        execution time.
    * `full_isolation` defaults to `True`: This ensures that each test runs
        in isolation, typically within its own transaction that is rolled back,
        preventing test interference.
    * Configuration via environment variables: Many default behaviors can be
        overridden using environment variables prefixed with `EDGY_TESTCLIENT_`.
    """

    # Class-level attribute to store the default test prefix for database names.
    testclient_default_test_prefix: str = default_test_prefix

    # Determine if lazy setup is enabled by default, configurable via environment variable.
    # Reads "EDGY_TESTCLIENT_LAZY_SETUP" and defaults to "true".
    testclient_default_lazy_setup: bool = (
        os.environ.get("EDGY_TESTCLIENT_LAZY_SETUP", "true") or ""
    ).lower() == "true"
    # Determine if force rollback is enabled by default, configurable via environment variable.
    # Reads "EDGY_TESTCLIENT_FORCE_ROLLBACK" and defaults to "false".
    testclient_default_force_rollback: bool = (
        os.environ.get("EDGY_TESTCLIENT_FORCE_ROLLBACK") or ""
    ).lower() == "true"
    # Determine if an existing database should be used by default, configurable via env var.
    # Reads "EDGY_TESTCLIENT_USE_EXISTING" and defaults to "false".
    testclient_default_use_existing: bool = (
        os.environ.get("EDGY_TESTCLIENT_USE_EXISTING") or ""
    ).lower() == "true"
    # Determine if the database should be dropped by default, configurable via environment variable.
    # Reads "EDGY_TESTCLIENT_DROP_DATABASE" and defaults to "false".
    testclient_default_drop_database: bool = (
        os.environ.get("EDGY_TESTCLIENT_DROP_DATABASE") or ""
    ).lower() == "true"
    # Determine if full isolation is enabled by default, configurable via environment variable.
    # Reads "EDGY_TESTCLIENT_FULL_ISOLATION" and defaults to "true".
    testclient_default_full_isolation: bool = (
        os.environ.get("EDGY_TESTCLIENT_FULL_ISOLATION", "true") or ""
    ).lower() == "true"
