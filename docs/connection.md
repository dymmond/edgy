# Connection Management

Using Edgy is designed to be straightforward, but understanding connection management is crucial for optimal performance and stability.

Edgy is built on SQLAlchemy Core, but it's an asynchronous implementation. This raises questions about its integration with popular frameworks like [Esmerald](https://esmerald.dymmond.com), Starlette, or FastAPI.

Edgy is framework-agnostic, meaning it can be seamlessly integrated into any framework that supports lifecycle events.

## Lifecycle Events

Lifecycle events are common in frameworks built on Starlette, such as [Esmerald](https://esmerald.dymmond.com) and FastAPI. Other frameworks may offer similar functionality through different mechanisms.

The most common lifecycle events include:

* **on_startup**
* **on_shutdown**
* **lifespan**

This document focuses on `lifespan`, which is widely used.

## Hooking Database Connections into Your Application

Integrating database connections is as simple as incorporating them into your framework's lifecycle events.

For illustrative purposes, we'll use [Esmerald](https://esmerald.dymmond.com). However, the principles apply to any framework.

Using ASGI integration:

```python hl_lines="8-12"
{!> ../docs_src/connections/asgi.py !}
```

Manual integration (applicable to all frameworks):

```python hl_lines="11-12"
{!> ../docs_src/connections/simple.py !}
```

Using an asynchronous context manager:

```python
{!> ../docs_src/connections/asynccontextmanager.py !}
```

Once the connection is integrated into your application's lifecycle, you can use the ORM throughout your application. Failing to do so will result in performance warnings, as the databasez backend will be reinitialized for each operation.

You can also define additional database connections in the registry and switch between them.

## Django Integration

Django doesn't natively support the lifespan protocol. Therefore, we provide a keyword parameter for manual handling.

```python
{!> ../docs_src/connections/django.py !}
```

## Manual Integration

The `__aenter__` and `__aexit__` methods can be called as `connect` and `disconnect`. However, using context managers is recommended for simpler error handling.

```python
{!> ../docs_src/connections/manual.py !}
```

This approach is suitable for integration via `on_startup` and `on_shutdown`.

```python
{!> ../docs_src/connections/manual_esmerald.py !}
```

## `DatabaseNotConnectedWarning`

This warning appears when an unconnected `Database` object is used.

Despite the warning being non-fatal, you should establish proper connections as demonstrated above. Synchronous environments require additional care.

!!! Note
    Ensure that `Database` objects passed via `using` are connected. They are not guaranteed to be connected outside of `extra`.

## Integration in Synchronous Environments

When the framework is synchronous and no asynchronous loop is active, we can use `run_sync`. It's necessary to create an asynchronous environment using the `with_async_env` method of the registry. Otherwise, you'll encounter performance issues and `DatabaseNotConnectedWarning` warnings. `run_sync` calls must occur within the scope of `with_async_env`. `with_async_env` is re-entrant and accepts an optional loop parameter.

```python
{!> ../docs_src/connections/contextmanager.py !}
```

To maintain the loop for performance reasons, you can wrap the server worker loop or, for single-threaded servers, the server loop that runs the application. Alternatively, you can keep the asyncio event loop alive, which is easier for synchronous-first frameworks like Flask. Here's an example that's multi-threading safe.

```python
{!> ../docs_src/connections/contextmanager_with_loop.py !}
```

That was complicated, right? Let's unroll it in a simpler example with explicit loop cleanup.

```python
{!> ../docs_src/connections/contextmanager_with_loop_and_cleanup.py !}
```

Note: `with_async_env` internally calls `__aenter__` and `__aexit__`. Therefore, the database is connected during the `with` scope of `with_async_env`. This means you can use `run_sync` and run commands in another loop (e.g., via `asyncio.run`). Everything works without raising `DatabaseNotConnectedWarning`. This is used, for example, in `edgy shell`.

## `run_sync` Function

`run_sync` requires further explanation. It integrates with the asynchronous environment created by `with_async_env` and prefers checking for an active running loop (unless an explicit loop is provided). If an active loop is found, a subloop is created, which is only terminated when the found loop (or explicit loop) is garbage collected. If an idling loop is found, it's reused instead of creating a subloop.

What is a subloop?

A subloop is an event loop running in a separate thread. This allows multiple event loops to run concurrently. They are removed when the parent event loop is garbage collected.

However, given that event loops can be sticky, we additionally check if the old loop has stopped.

## Querying Other Schemas

Edgy supports querying other schemas. Refer to the [tenancy](./tenancy/edgy.md) section for details.

## Multiple Connections

The Edgy Registry accepts an `extra` parameter for defining named additional `Database` objects or strings. Including them here ensures they're connected and disconnected appropriately.

You can switch between them using [using](./queries/queries.md#selecting-the-database-and-schema).

## Migrate from flask-migrate

See [Migrations](./migrations/migrations.md#migrate-from-flask-migrate) for more informations.

## Note

Check the [tips and tricks](./tips-and-tricks.md) and learn how to make your connections even cleaner.
