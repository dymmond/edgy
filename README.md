# Edgy

<p align="center">
  <a href="https://edgy.dymmond.com"><img src="https://res.cloudinary.com/tarsild/image/upload/v1690804138/packages/edgy/logo_wvmjxz.png" alt='Edgy'></a>
</p>

<p align="center">
    <em>🔥 The perfect ORM to work with complex databases 🔥</em>
</p>

<p align="center">
<a href="https://github.com/dymmond/edgy/workflows/Test%20Suite/badge.svg?event=push&branch=main" target="_blank">
    <img src="https://github.com/dymmond/edgy/workflows/Test%20Suite/badge.svg?event=push&branch=main" alt="Test Suite">
</a>

<a href="https://pypi.org/project/edgy" target="_blank">
    <img src="https://img.shields.io/pypi/v/edgy?color=%2334D058&label=pypi%20package" alt="Package version">
</a>

<a href="https://pypi.org/project/edgy" target="_blank">
    <img src="https://img.shields.io/pypi/pyversions/edgy.svg?color=%2334D058" alt="Supported Python versions">
</a>
</p>

---

**Documentation**: [https://edgy.dymmond.com][edgy] 📚

**Source Code**: [https://github.com/dymmond/edgy](https://github.com/dymmond/edgy)

---

## Motivation

From the same author of [Saffier][saffier], Edgy is also an ORM but different from its predecessor.
Saffier is more of a Generic ORM for probably 99.9% of every single day application and works
perfectly well with it, whereas **Edgy** is also that and more.

Edgy comes with batteries included thanks to Pydantic so that means your [models][models] are 100%
Pydantic which also means you get all the benefits of the technology (like automatic validations...)
out of the box with the need of building independent schemas to validate those fields before injest
them into a database.

**Was it already mentioned that Edgy is extremely fast? Well, it is!**

Almost every project, in one way or another uses one (or many) databases. An ORM is simply an mapping
of the top of an existing database. ORM extends for Object Relational Mapping and bridges object-oriented
programs and relational databases.

Two of the most well known ORMs are from Django and SQLAlchemy. Both have their own strenghts and
weaknesses and specific use cases.

This ORM is built on the top of SQLAlchemy core and aims to simplify the way the setup and queries
are done into a more common and familiar interface with the power of **Pydantic**.

## Edgy

Edgy is some sort of a fork from [Saffier][saffier] but rewritten at its core fully in Pydantic 🔥.

This was necessary because Saffier although serving 99.9% of the daily use cases, there was still
a great need to add automatic validations and performance, so instead of rewritting
[Saffier][saffier] and risking breaking existing use cases already in place, a brand new shiny ORM
came to be 😁.

Edgy leverages the power of **Pydantic** while offering a friendly, familiar and easy to use interface.

This ORM was designed to be flexible and compatible with pretty much every ASGI framework, like
[Esmerald](https://esmerald.dymmond.com), Starlette, FastAPI, Sanic, Quart... With simple pluggable
design thanks to its origins.

## Features

While adopting a familiar interface, it offers some cool and powerful features on the top of
SQLAlchemy core.

### Key features

* **Model inheritance** - For those cases where you don't want to repeat yourself while maintaining
integrity of the models.
* **Abstract classes** - That's right! Sometimes you simply want a model that holds common fields
that doesn't need to created as a table in the database.
* **Meta classes** - If you are familiar with Django, this is not new to you and Edgy offers this
in the same fashion.
* **Managers** - Versatility at its core, you can have separate managers for your models to optimise
specific queries and querysets at ease.
* **Filters** - Filter by any field you want and need.
* **Model operators** - Classic operations such as `update`, `get`, `get_or_none`, `bulk_create`,
`bulk_update`, `values`, `values_list`, `only`, `defer` and a lot more.
* **Relationships made it easy** - Support for `OneToOne`, `ForeignKey` and `ManyToMany` in the same Django style.
* **Constraints** - Unique constraints through meta fields.
* **Indexes** - Unique indexes through meta fields.
* **Native test client** - We all know how hard it can be to setup that client for those tests you
need so we give you already one.
* **Multi-tenancy** - Edgy supports multi-tenancy and even offers a possible solution to be used
out of the box if you don't want to waste time.

And a lot more you can do here.

## Migrations

Since **Edgy**, like [Saffier][saffier], it is built on the top of
[SQLAlchemy core](https://docs.sqlalchemy.org/en/20/core/) and brings its own native migration
system running on the top of [Alembic][alembic] but making it a
lot easier to use and more pleasant for you.

Have a look at the [migrations](./migrations/migrations.md) for more details.

## Installation

To install Edgy, simply run:

```shell
$ pip install edgy
```

You can pickup your favourite database driver by yourself or you can run:

**Postgres**

```shell
$ pip install edgy[postgres]
```

**MySQL/MariaDB**

```shell
$ pip install edgy[mysql]
```

**SQLite**

```shell
$ pip install edgy[sqlite]
```

**MSSQL**

```shell
$ pip install edgy[mssql]
```

## Quick Start

The following is an example how to start with **Edgy** and more details and examples can be
found throughout the documentation.

**Use** `ipython` **to run the following from the console, since it supports** `await`.

```python
import edgy
from edgy import Database, Registry

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


class User(edgy.Model):
    """
    The User model to be created in the database as a table
    If no name is provided the in Meta class, it will generate
    a "users" table for you.
    """

    id: int = edgy.IntegerField(primary_key=True)
    is_active: bool = edgy.BooleanField(default=False)

    class Meta:
        registry = models


# Create the db and tables
# Don't use this in production! Use Alembic or any tool to manage
# The migrations for you
await models.create_all()  # noqa

await User.query.create(is_active=False)  # noqa

user = await User.query.get(id=1)  # noqa
print(user)
# User(id=1)
```

As stated in the example, if no `tablename` is provided in the `Meta` class, Edgy automatically
generates the name of the table for you by pluralising the class name.

### Note

Edgy model declaration with `typing` is **merely visual**. The validations of the fields
are not done by the typing of the attribute of the models but from the **edgy fields**.

Which means you don't need to worry about the *wrong* typing as long as you declare the correct
field type.

So does that mean pydantic won't work if you don't declare the type? Absolutely not. Internally
Edgy runs those validations through the declared fields and the Pydantic validations are done
exactly in the same way you do a normal Pydantic model.

Nothing to worry about!

Let us see an example.

**With field typing**

```python
import edgy
from edgy import Database, Registry

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


class User(edgy.Model):
    """
    The User model to be created in the database as a table
    If no name is provided the in Meta class, it will generate
    a "users" table for you.
    """

    id: int = edgy.IntegerField(primary_key=True)
    is_active: bool = edgy.BooleanField(default=False)

    class Meta:
        registry = models
```

**Without field typing**

```python
import edgy
from edgy import Database, Registry

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


class User(edgy.Model):
    """
    The User model to be created in the database as a table
    If no name is provided the in Meta class, it will generate
    a "users" table for you.
    """

    id = edgy.IntegerField(primary_key=True)
    is_active = edgy.BooleanField(default=False)

    class Meta:
        registry = models
```

It does not matter if you type or not, Edgy knows what and how to validate via `edgy fields` like
`IntegerField` or `BooleanField` or any other field.

## Connect your application

Do you want to have more complex structures and connect to your favourite framework? Have a look
at [connections](./connection.md) to understand how to do it properly.

## `Esmerald` ecosystem

This does not mean that only works with Esmerald! Edgy is also framework agnostic but the author
of Edgy is the same of Saffier and Esmerald which makes it nicer to integrate directly with Esmerald.

How could you integrate `Edgy` with Esmerald (or any other framework)?

Let us see an example. Since Edgy is fully Pydantic that means we can perform tasks directly.

```python
from esmerald import Esmerald, Gateway, post

import edgy
from edgy.testclient import DatabaseTestClient as Database

database = Database("sqlite:///db.sqlite")
models = edgy.Registry(database=database)


class User(edgy.Model):
    id: int = edgy.IntegerField(primary_key=True)
    name: str = edgy.CharField(max_length=100)
    email: str = edgy.EmailField(max_length=100)
    language: str = edgy.CharField(max_length=200, null=True)
    description: str = edgy.TextField(max_length=5000, null=True)

    class Meta:
        registry = models


@post("/create")
async def create_user(data: User) -> User:
    """
    You can perform the same directly like this
    as the validations for the model (nulls, mandatories, @field_validators)
    already did all the necessary checks defined by you.
    """
    user = await data.save()
    return user


app = Esmerald(
    routes=[Gateway(handler=create_user)],
    on_startup=[database.connect],
    on_shutdown=[database.disconnect],
)

```

The response of the API `/create` should have a format similar to this (assuming the post with the following payload as well):

```json
{
    "id": 1,
    "name": "Edgy",
    "email": "edgy@esmerald.dev",
    "language": "EN",
    "description": "A description",
}
```

**All the examples of this documentation will be using field typing but it is up to you if you want to use them or not.**

**Exciting!**

In the documentation we go deeper in explanations and examples, this was just to warm up. 😁


[edgy]: https://edgy.dymmond.com
[saffier]: https://saffier.tarsild.io
[models]: ./models.md
[alembic]: https://alembic.sqlalchemy.org/en/latest/
