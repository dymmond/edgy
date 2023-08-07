# Transactions

Saffier using `databases` package allows also the use of transacations in a very familiar way for
a lot of the users.

You can see a transaction as atomic, which means, when you need to save everything or fail all.

!!! Tip
    Check more information about [atomicity](https://en.wikipedia.org/wiki/Atomicity_(database_systems)#:~:text=An%20atomic%20transaction%20is%20an,rejecting%20the%20whole%20series%20outright) to get familiar with the concept.

There are three ways of using the transaction in your application:

* As a [decorator](#as-a-decorator)
* As a [context manager](#as-a-context-manager)

The following explanations and examples will take in account the following:

Let us also assume we want to create a `user` and a `profile` for that user in a simple endpoint.

!!! danger
    If you are trying to setup your connection within your application and have faced some errors
    such as `AssertationError: DatabaseBackend is not running`, please see the [connection](./connection.md)
    section for more details and how to make it properly.

```python
{!> ../docs_src/transactions/models.py!}
```

## As a decorator

This is probably one of the less common ways of using transactions but still very useful if you
want all of your endpoint to be atomic.

We want to create an endpoint where we save the `user` and the `profile` in one go. Since the
author of Saffier is the same as [Esmerald](https://esmerald.dymmond.com), it makes sense to use
it as example.

**You can use whatever you want, from Starlette to FastAPI. It is your choice**.

```python hl_lines="18"
{!> ../docs_src/transactions/decorator.py!}
```

As you can see, the whole endpoint is covered to work as one transaction. This cases are rare but
still valid to be implemented.

## As a context manager

This is probably the most common use-case for the majority of the applications where within a view
or an operation, you will need to make some transactions that need atomocity.

```python hl_lines="22"
{!> ../docs_src/transactions/context_manager.py!}
```

## Important notes

Saffier although running on the top of [Databases](https://www.encode.io/databases/) it varies in
many aspects and limits some of the unecessary `free-style` usage to make sure it keeps its
consistance.

If you are interested in knowing more about the low-level APIs of databases,
[check out](https://www.encode.io/databases/) their [documentation](https://www.encode.io/databases/).
