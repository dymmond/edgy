# Debugging & Performance

Edgy provides several debugging features, also through databasez. It aims to maintain an efficient event loop and execute queries in the most performant manner. For example, asyncio pools are thread-protected in databasez, allowing connections to the database to remain open.

However, this requires that databases and registries are not simply discarded but kept open during operation. To ensure a proper lifespan, a reference counter is used.

When the reference count drops to 0, the database is uninitialized, and connections are closed.

Reopening the database is possible but inefficient and can lead to side effects, especially with the `DatabaseTestClient`. The `DatabaseNotConnectedWarning` exists to address this.

### Getting the SQL Query

The `QuerySet` contains a cached debug property named `sql`, which displays the `QuerySet` as a query with inserted blanks.

### Performance Warnings (`DatabaseNotConnectedWarning`)

The `DatabaseNotConnectedWarning` is likely the most common warning in Edgy.

It is intentional and serves to guide users in improving their code, preventing unnecessary disposal of engines. Additionally, it can lead to difficult-to-debug errors in test environments due to a missing database (e.g., `drop_database` parameter).

Edgy issues a `DatabaseNotConnectedWarning` when used without a connected database. To suppress it, wrap the affected code in a database scope:

```python
await model.save()
# becomes
async with model.database:
    await model.save()
```

If the warning is completely unwanted despite the performance impact, you can filter it:

```python
import warnings
from edgy.exceptions import DatabaseNotConnectedWarning

with warnings.catch_warnings(action="ignore", category=DatabaseNotConnectedWarning):
    await model.save()
```

It inherits from `UserWarning`, so filtering `UserWarning` is also possible.

However, silencing the warning is generally not recommended.

## Many Connections

If the database is slow due to numerous Edgy connections, and no `DatabaseNotConnectedWarning` was raised, it indicates that deferred fields are being accessed. This includes `ForeignKey` relationships where models are not prefetched via `select_related`.

### Debugging Deferred Loads

For debugging purposes (at the cost of deferred loads), you can set the `ContextVariable` `edgy.core.context_vars.MODEL_GETATTR_BEHAVIOR` to `"passdown"` instead of `"load"`.

This will cause crashes if an implicitly loaded variable is accessed.

### Optimizing `ReflectedModel`

`ReflectedModel` has the issue that not all database fields are known. Therefore, testing if an optional attribute is available via `getattr`/`hasattr` will trigger a load first.

There are two ways to work around this:

1.  Use the model instance dictionary instead (e.g., `model.__dict__.get("foo")` or `"foo" in model.__dict__`).
2.  Add the optional available attributes to `__no_load_trigger_attrs__`. They will no longer trigger a load.

## Hangs

Hangs typically occur when only **one** connection is available or the database is blocked. This is usually easily debuggable, often with the same methods mentioned earlier, due to the same reasons. If there are hard-to-debug stack traces, it suggests that threads and asyncio are mixed.

Here, you can enforce hard timeouts via the `DATABASEZ_RESULT_TIMEOUT` environment variable.
