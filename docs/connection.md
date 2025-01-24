# Connection

Using edgy is extremely simple and easy to do but there are some steps you might want to take
into consideration like connections and what it can happen if this is not done properly.

Edgy is on SQLAlechemy core but is an `async` version of it and therefore what happens if you
want to use it within your favourite frameworks like [Esmerald](https://esmerald.dymmond.com),
Starlette or even FastAPI?

Well, Edgy is framework agnostic so it will fit in any framework you want, even in those that
are not listed above that support **lifecycle events**.

## Lifecycle events

These are very common amongst those frameworks that are based on Starlette, like
[Esmerald](https://esmerald.dymmond.com) or FastAPI but other might have a similar approach but
using different approaches.

The common lifecycle events are the following:

* **on_startup**
* **on_shutdown**
* **lifespan**

This document will focus on the one more commonly used, `lifespan`.

## Hooking your database connection into your application

Hooking a connection is as easy as putting them inside those events in your framework.

For this example, since the author is the same as the one of [Esmerald](https://esmerald.dymmond.com),
we will be using it for explanatory purposes, feel free to apply the same principle in your favourite
framework.

with the ASGI integration:

```python hl_lines="8-12"
{!> ../docs_src/connections/asgi.py !}
```

Or doing it manually (that applies to every framework):


```python hl_lines="11-12"
{!> ../docs_src/connections/simple.py !}
```

Or just as an async contexmanager

```python
{!> ../docs_src/connections/asynccontextmanager.py !}
```

And that is pretty much this. Once the connection is hooked into your application lifecycle.
Otherwise you will get warnings about decreased performance because the databasez backend is not connected and will be
reininitialized for each operation.

You are now free to use the ORM anywhere in your application. As well as extra defined database connections in registry.

## Django integration

Django currently doesn't support the lifespan protocol. So we have a keyword parameter to handle it ourselves.

```python
{!> ../docs_src/connections/django.py !}
```

## Manual integration

The `__aenter__` and `__aexit__` methods support also being called like `connect` and `disconnect`.
It is however not recommended as contextmanagers have advantages in simpler error handling.

```python
{!> ../docs_src/connections/manual.py !}
```

You can use this however for an integration via `on_startup` & `on_shutdown`.

```python
{!> ../docs_src/connections/manual_esmerald.py !}
```

## `DatabaseNotConnectedWarning` warning

This warning appears, when an unconnected Database object is used for an operation.

Despite bailing out the warning `DatabaseNotConnectedWarning` is raised.
You should connect correctly like shown above.
In sync environments it is a bit trickier.

!!! Note
    When passing Database objects via using, make sure they are connected. They are not necessarily connected
    when not in extra.

## Integration in sync environments

When the framework is sync by default and no async loop is active we can fallback to `run_sync`.
It is required to build an async evnironment via the `with_async_env` method of registry. Otherwise
we run in bad performance problems and have `DatabaseNotConnectedWarning` warnings.
`run_sync` calls **must** happen within the scope of `with_async_env`. `with_async_env` is reentrant and has an optional loop parameter.

```python
{!> ../docs_src/connections/contextmanager.py !}
```
To keep the loop alive for performance reasons we can either wrap the server worker loop or in case of
a single-threaded server the server loop which runs the application. As an alternative you can also keep the asyncio eventloop alive.
This is easier for sync first frameworks like flask.
Here an example which is even multithreading save.

```python
{!> ../docs_src/connections/contextmanager_with_loop.py !}
```

That was complicated, huh? Let's unroll it in a simpler example with explicit loop cleanup.


```python
{!> ../docs_src/connections/contextmanager_with_loop_and_cleanup.py !}
```

Note: `with_async_env` also calls `__aenter__` and `__aexit__` internally. So the database is connected during the
with scope spanned by `with_async_env`.

## `run_sync` function

`run_sync` needs a bit more explaination. On the one hand it hooks into the async environment
spawned by `with_async_env`. On the other hand it prefers checking for an active running loop (except if an explicit loop was provided).
If an active loop was found, a subloop is spawned which is only torn down when the found loop (or explicit provided loop) was collected.
When an idling loop was found, it will be reused, instead of creating a subloop.

What is a subloop?

A subloop is an eventloop running in an extra thread. This enables us to run multiple eventloops simultanously.
They are removed when the parent eventloop is garbage collected.

However given that the eventloops are quite sticky despite they should have been garbage collected
we additionally poll if the old loop had stopped.


## Querying other schemas

Edgy supports that as well. Have a look at the [tenancy](./tenancy/edgy.md) section for more details.

## Having multiple connections

Edgy Registry has an extra parameter where named additional Database objects or strings can be defined. Having them there
is useful because they will be connected/disconnected too.

You can switch to them on the fly via [using](./queries/queries.md#selecting-the-database-and-schema).

## Migrate from flask-migrate

See [Migrations](./migrations/migrations.md#migrate-from-flask-migrate) for more informations.

## Note

Check the [tips and tricks](./tips-and-tricks.md) and learn how to make your connections even cleaner.
