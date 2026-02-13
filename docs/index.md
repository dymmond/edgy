---
hide:
  - navigation
---

# Edgy

<p align="center">
  <a href="https://edgy.dymmond.com"><img src="https://res.cloudinary.com/tarsild/image/upload/v1690804138/packages/edgy/logo_wvmjxz.png" alt='Edgy'></a>
</p>

<p align="center">
    <em>🔥 The perfect ORM to work with complex databases 🔥</em>
</p>

<p align="center">
<a href="https://github.com/dymmond/edgy/actions/workflows/test-suite.yml/badge.svg?event=push&branch=main" target="_blank">
    <img src="https://github.com/dymmond/edgy/actions/workflows/test-suite.yml/badge.svg?event=push&branch=main" alt="Test Suite">
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
[Ravyn](https://ravyn.dymmond.com), Starlette, FastAPI, Sanic, Quart... With simple pluggable
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

## Quick Start

The following is an example how to start with **Edgy** and more details and examples can be
found throughout the documentation.

**Use** `ipython` **to run the following from the console, since it supports** `await`.

```python
{!> ../docs_src/quickstart/example1.py!}
```

As stated in the example, if no `tablename` is provided in the `Meta` class, Edgy automatically
generates the name of the table for you by pluralising the class name.

### Note

{! ../docs_src/shared/notes.md !}

## `Ravyn` ecosystem

This does not mean that only works with Ravyn! Edgy is also framework agnostic but the author
of Edgy is the same of Saffier and Ravyn which makes it nicer to integrate directly with Ravyn.

How could you integrate `Edgy` with Ravyn (or any other framework)?

Let us see an example. Since Edgy is fully Pydantic that means we can perform tasks directly.

```python hl_lines="28"
{!> ../docs_src/quickstart/ravyn.py!}
```

The response of the API `/create` should have a format similar to this (assuming the post with the following payload as well):

```json
{
    "id": 1,
    "name": "Edgy",
    "email": "edgy@ravyn.dev",
    "language": "EN",
    "description": "A description",
}
```

## Connect your application

Do you want to have more complex structures and connect to your favourite framework? Have a look
at [connections](./connection.md) to understand how to do it properly.

**All the examples of this documentation will be using field typing but it is up to you if you want to use them or not.**

**Exciting!**

In the documentation we go deeper in explanations and examples, this was just to warm up. 😁

### Powered by

Worth mentioning who is helping us.

[![JetBrains logo.](https://resources.jetbrains.com/storage/products/company/brand/logos/jetbrains.svg)](https://jb.gg/OpenSourceSupport)


[edgy]: https://edgy.dymmond.com
[saffier]: https://saffier.tarsild.io
[models]: ./models.md
[alembic]: https://alembic.sqlalchemy.org/en/latest/
