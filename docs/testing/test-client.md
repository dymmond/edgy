# Test Client: Streamlining Database Testing in Edgy

Have you ever struggled with testing your database interactions, ensuring your model tests target a specific test database instead of your development database? This is a common challenge, often requiring significant setup. Edgy addresses this with its built-in `DatabaseTestClient`, simplifying your database testing workflow.

Before proceeding, ensure you have the Edgy test client installed with the necessary dependencies:

```bash
$ pip install edgy[test]
```

## DatabaseTestClient

The `DatabaseTestClient` is designed to streamline database testing, automating the creation and management of test databases.

```python
from edgy.testclient import DatabaseTestClient
```

### Parameters

* **url**: The database URL, either as a string or a `databases.DatabaseURL` object.

    ```python
    from databases import DatabaseURL
    ```

* **force_rollback**: Ensures all database operations are executed within a transaction that rolls back upon disconnection.

    <sup>Default: `False`</sup>

* **lazy_setup**: Sets up the database on the first connection, rather than during initialization.

    <sup>Default: `True`</sup>

* **use_existing**: Uses an existing test database if it was previously created and not dropped.

    <sup>Default: `False`</sup>

* **drop_database**: Drops the test database after the tests have completed.

    <sup>Default: `False`</sup>

* **test_prefix**: Allows a custom test database prefix. Leave empty to use the URL's database name with a default prefix.

    <sup>Default: `testclient_default_test_prefix` (defaults to `test_`)</sup>

### Configuration via Environment Variables

Most default parameters can be overridden using capitalized environment variables prefixed with `EDGY_TESTCLIENT_`.

For example: `EDGY_TESTCLIENT_DEFAULT_PREFIX=foobar` or `EDGY_TESTCLIENT_FORCE_ROLLBACK=true`.

This is particularly useful for configuring tests in CI/CD environments.

### Usage

The `DatabaseTestClient` is designed to be familiar to users of Edgy's `Database` object, as it extends its functionality with testing-specific features.

Consider a database URL like this:

```bash
DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/my_db"
```

In this case, the database name is `my_db`. When using the `DatabaseTestClient`, it automatically targets a test database named `test_my_db`.

Here's an example of how to use it in a test:

```python title="tests.py" hl_lines="14"
{!> ../docs_src/testing/testclient/tests.py !}
```

#### Explanation

This example demonstrates a test using `DatabaseTestClient`. The client ensures that all database operations within the test are performed on a separate test database, `test_my_db` in this case.

The `drop_database=True` parameter ensures that the test database is deleted after the tests have finished running, preventing the accumulation of test databases.

This approach provides a clean and isolated testing environment, ensuring that your tests do not interfere with your development or production databases.
