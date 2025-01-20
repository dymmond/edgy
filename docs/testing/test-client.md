# Test Client

I'm sure that you already faced the problem with testing your database anmd thinking about a way
of making sure the tests against models would land in a specific targeted database instead of the
one used for development, right?

Well, at least I did and it is annoying the amount of setup required to make it happen and for that
reason, Edgy provides you already one client that exctly that job for you.

Before continuing, make sure you have the Edgy test client installed with the needed
requirements.

```
$ pip install edgy[test]
```

## DatabaseTestClient

This is the client you have been waiting for. This object does a lot of magic for you and will
help you manage those stubborn tests that should land on a `test_` database.

```python
from edgy.testclient import DatabaseTestClient
```

### Parameters

* **url** - The database url for your database. This can be in a string format or in a
`databases.DatabaseURL`.

    ```python
    from databases import DatabaseURL
    ```

* **force_rollback** - This will ensure that all database connections are run within a transaction
that rollbacks once the database is disconnected.

    <sup>Default: `False`</sup>

* **lazy_setup** - This sets up the db first up on connect not in init.

    <sup>Default: `True`</sup>


* **use_existing** - Uses the existing `test_` database if previously created and not dropped.

    <sup>Default: `False`</sup>

* **drop_database** - Ensures that after the tests, the database is dropped.

    <sup>Default: `False`</sup>

* **test_prefix** - Allow a custom test prefix or leave empty to use the url instead without changes.

    <sup>Default: `testclient_default_test_prefix` (defaults to `test_`)</sup>

### Configuration via Environment

Most parameters defaults can be changed via capitalized environment names with `EDGY_TESTCLIENT_`.

E.g. `EDGY_TESTCLIENT_DEFAULT_PREFIX=foobar` or `EDGY_TESTCLIENT_FORCE_ROLLBACK=true`.

This is used for the tests.

### How to use it

This is the easiest part because is already very familiar with the `Database` used by Edgy. In
fact, this is an extension of that same object with a lot of testing flavours.

Let us assume you have a database url like this following:

```shell
DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/my_db"
```

We know the database is called `my_db`, right?

When using the `DatabaseTestClient`, the client will ensure the tests will land on a `test_my_db`.

Pretty cool, right?

Nothing like an example to see it in action.

```python title="tests.py" hl_lines="14"
{!> ../docs_src/testing/testclient/tests.py !}
```

#### What is happening

Well, this is rather complex test and actually a real one from Edgy and what you can see is
that is using the `DatabaseTestClient` which means the tests against models, fields or whatever
database operation you want will be on a `test_` database.

But you can see a `drop_database=True`, so what is that?

Well `drop_database=True` means that by the end of the tests finish running, drops the database
into oblivion.
