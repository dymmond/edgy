# Transactions in Edgy

Edgy, leveraging the `databasez` package, provides robust transaction support that will feel familiar to many developers. Transactions ensure atomicity, meaning that a series of database operations either all succeed or all fail, maintaining data consistency.

!!! Tip
    For a deeper understanding of atomicity, refer to the [Atomicity in Database Systems](https://en.wikipedia.org/wiki/Atomicity_(database_systems)#:~:text=An%20atomic%20transaction%20is%20an,rejecting%20the%20whole%20series%20outright) documentation.

Edgy offers three primary ways to manage transactions:

The following examples will use a scenario where we create a `user` and a `profile` for that user within a single endpoint.

!!! danger
    If you encounter `AssertionError: DatabaseBackend is not running`, please consult the [connection](./connection.md) section for proper connection setup.

```python
{!> ../docs_src/transactions/models.py!}
```

## As a Decorator

Using transactions as decorators is less common but useful for ensuring entire endpoints are atomic.

Consider an Esmerald endpoint (but this can be any web framework) that creates a `user` and a `profile` in one atomic operation:

```python hl_lines="18"
{!> ../docs_src/transactions/decorator.py!}
```

In this case, the `@transaction()` decorator ensures that the entire endpoint function executes within a single transaction. This approach is suitable for cases where all operations within a function must be atomic.

## As a Context Manager

Context managers are the most common way to manage transactions, especially when specific sections of code within a view or operation need to be atomic.
It is recommended to use the model or queryset transaction method.
This way the transaction of the right database is used.

```python hl_lines="22"
{!> ../docs_src/transactions/context_manager.py!}
```

Using the current active database of a QuerySet:

```python hl_lines="23"
{!> ../docs_src/transactions/context_manager2.py!}
```

You can also access the database and start the transaction directly:

```python hl_lines="23"
{!> ../docs_src/transactions/context_manager_direct.py!}
```

This ensures that the operations within the `async with` block are executed atomically. If any operation fails, all changes are rolled back.

## Important Notes

Edgy, while built on top of [Databasez](https://databasez.dymmond.com/), offers unique features beyond those provided by SQLAlchemy. These include JDBC support and compatibility with mixed threading/async environments.

For more information on the low-level APIs of Databasez, refer to the [Databasez repository](https://github.com/dymmond/databasez) and its [documentation](https://databasez.dymmond.com/).
