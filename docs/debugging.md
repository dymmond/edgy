# Debugging & Performance

Edgy has several debug features, also through databasez. It tries also to keep it's eventloop and use the most smartest way
to execute a query performant.
For example asyncio pools are thread protected in databasez so it is possible to keep the connections to the database open.

But this requires that databases and registries are not just thrown away but kept open during the operation. For getting a
sane lifespan a reference counter are used.

When dropped to 0 the database is uninitialized and drops the connections.

There is no problem re-opening the database but it is imperformant and can have side-effects especcially with the `DatabaseTestClient`.
For this the `DatabaseNotConnectedWarning` warning exist.

## `DatabaseNotConnectedWarning` warning

The most common warning in edgy is probably the `DatabaseNotConnectedWarning` warning.

It is deliberate and shall guide the user to improve his code so he doesn't throws away engines unneccessarily.
Also it could lead in test environments to hard to debug errors because of a missing database (drop_database parameter).

## Many connections

If the database is slow due to many connections by edgy and no `DatabaseNotConnectedWarning` warning was raised
it indicates that deferred fields are accessed.
This includes ForeignKey, which models are not prefetched via `select_related`.

### Debugging deferred loads

For debugging purposes (but sacrificing deferred loads with it) you can set the ContextVariable
`edgy.core.context_vars.MODEL_GETATTR_BEHAVIOR` to `"passdown"` instead of `"load"`.

This will lead to crashes in case an implicit loaded variable is accessed.

### Optimizing ReflectedModel

ReflectedModel have the problem that not all database fields are known. Therefor testing if an optional attribute
is available via `getattr`/`hasattr` will lead to a load first.

There are two ways to work around:

1. Use the model instance dict instead (e.g. `model.__dict__.get("foo")` or `"foo" in model.__dict__`).
2. Add the optional available attributes to `__no_load_trigger_attrs__`. They won't trigger an load anymore.

## Hangs

Hangs typical occur when there is only **one** connection available or the database is blocked.
This is normally easily debuggable often with the same ways like mentioned before because of the same reasons.
If it has hard to debug stack traces, it seems that threads and asyncio are mixed.

Here you can enforce hard timeouts via the `DATABASEZ_RESULT_TIMEOUT` environment variable.
