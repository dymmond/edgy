# Tenancy

Sometimes you might want to query a different database or schema because might be convenient to
get data from two different sources.

Querying two different databases or schemas its not so uncommon as you might think and to this
we can sometimes refer to **multi-tenancy** or simply two different data sources.

## What is multi-tenancy

When implementing multi tenancy architecture there are many factors to consider and there are three common ways:

1. **Shared schemas** - The data of all users are shared within the same schema and filtered by common IDs or whatever that is unique to the platform.
This is not so great for GDPR (Europe) or similar in different countries.
2. **Shared database, different Schemas** - The user's data is split by different schemas but live on the same database.
3. **Different databases** - The user's data or any data live on different databases.

Edgy has three different ways of achieving this in a simple and clean fashion.

1. Using the [using](#using) in the queryset.
2. Using the [using_with_db](#what-is-multi-tenancy) in the queryset.
3. Using the [set_tenant](#set-tenant) as global.

You can also use the [Edgy helpers for schemas][schemas] if you need to use it.

### Using

This is probably the one that is more commonly used and probably the one you will be using more
often when querying different schemas or databases.

The using is simply an instruction telling to ***use this schema*** to query the data instead of
the default set in the [registry][registry].

**Parameters**:

* **schema** - A string parameter with the name of the schema to query.

The syntax is quite simple.

```python
<Model>.query.using(<SCHEMA-NAME>).all()
```

This is not limited to the `all()` at all, you can use any of the available [query types](../queries/queries.md)
as well.

#### Example

Let us assume we have two different schemas inside the same database and those schemas have a table
called `User`.

* The schema `default` - The one that is automatically used if no schema is specified in the [registry][registry].
* The schema `other` - The one we also want to query.

```python
{!> ../docs_src/tenancy/using/schemas.py !}
```

Now we want to query the users from each schema.

**Querying the default**

As per normal approach, the query looks like this.

```python
User.query.all()
```

**Querying the main**

Query the users table from the `main` schema.

```python
User.query.using('main').all()
```

And that is it, really. Using its a simple shortcut that allows querying different schemas
without a lot of boilerplate.

### With with database

Now here it is where the things get interesting. What if you need/want to query a schema but from
a different database instead?

### Set tenant

[registry]: ../registry.md
[schemas]: ../registry.md#schemas
