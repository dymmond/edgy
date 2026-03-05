# Install and First Query

This guide gets you from zero to a running model query as quickly as possible.

## 1. Install Edgy

For SQLite:

```shell
$ pip install edgy[sqlite]
```

For Postgres:

```shell
$ pip install edgy[postgres]
```

## 2. Define Your First Model

The following example is enough to create a model, create a record, and read it back.

Use `ipython` so you can run `await` directly.

```python
{!> ../docs_src/quickstart/example1.py !}
```

## 3. Extend the Query

Now that your model works, try chaining a filter:

```python
users = await User.query.filter(is_active=False).order_by("id").all()
```

Then inspect only selected fields:

```python
user_rows = await User.query.only("id").values()
```

## 4. Understand What Happened

At a high level:

1. you declared a model bound to a registry,
2. Edgy translated model metadata to SQL,
3. QuerySet compiled and executed a query,
4. result rows were parsed back into model instances.

For the deeper runtime flow, read [Request and Query Lifecycle](../concepts/request-lifecycle.md).

## 5. Next Step

Continue with [First Migration Cycle](./first-migration-cycle.md) to make schema changes reproducible.

## See Also

* [Models](../models.md)
* [Queries](../queries/queries.md)
* [Connection Management](../connection.md)
* [Migrations](../migrations/migrations.md)
