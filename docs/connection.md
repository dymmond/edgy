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

This document will focus on the two more commonly used, `on_startup` and `on_shutdown`.

## Hooking your database connection into your application

Hooking a connection is as easy as putting them inside those events in your framework.

For this example, since the author is the same as the one of [Esmerald](https://esmerald.dymmond.com),
we will be using it for explanatory purposes, feel free to apply the same principle in your favourite
framework.

with the ASGI integration:

```python hl_lines="9"
{!> ../docs_src/connections/asgi.py !}
```

Or doing it manually (that applies to every framework):


```python hl_lines="11-12"
{!> ../docs_src/connections/simple.py !}
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
