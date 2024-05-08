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

### Using with database

Now here it is where the things get interesting. What if you need/want to query a schema but from
a different database instead? Well, that is possible with the use of the `using_with_db`.

{!> ../docs_src/shared/extra.md !}

### Using with `activate_schema`

!!! Warning
    This feature is experimental and might be inconsistent with the intended results. Use it at your
    own discretion.

This is an **alternative** to [using](#using) and serves solely as the purpose of avoiding
writing all the time `Model.query.using(...)`.

You can use `activate_schema(...)` and `deactivate_schema()` to tell the query to always query
a specific tenant, in other words, using the `activate_schema()` you don't need to constantly
write `using(...)`.

Importing is as simple as this:

```python
from edgy.core.db.querysets.mixins import activate_schema, deativate_schema
```

Let us see an example:

**With the classic .using()**

```python
# Using the 'main' schema

User.query.using('main').all()
User.query.using('main').filter(email__icontains="user@example.com")
User.query.using('main').get(pk=(1,))
```

**Using the activate_schema**

```python
# Using the 'main' schema
activate_schema("main")

# Query the 'User' from the 'main' schema
User.query.all()
User.query.filter(email__icontains="user@example.com")
User.query.get(pk=1)

# Deactivate the schema and default to the public
deactivate_schema("main")
```

### Set tenant

This is another way to create a global `tenant` for your application. Instead if [using](#using) or
[using_with_db](#using-with-database) you simply want to make sure that in your application you
want every request for a specific `tenant` to always hit their corresponding tenant data.

This is specially useful for multi-tenant applications where your tenant users will only see their
own data.

To use the `set_tenant` you can import it via:

```python
from edgy.core.db import set_tenant
```

!!! Tip
    Use the `set_tenant` in things like application middlewares or interceptors, right before
    reaching the API.

#### Practical case

The `set_tenant` can be somehow confusing without a proper example so let us run one 😁.

As usual, for this example [Esmerald][esmerald] will be used. This can be applied to any framework
of your choice of course.

**What are we building**:

- [Models](#models) - Some models that will help us out mapping a user with a tenant.
- [Middleware](#middleware) - Intercept the request and **set the corresponding tenant**.
- [API](#api) - The API that returns the data for a given tenant.

##### Models

Let us start with some models where we have a `Tenant`, a `User` model as well as a `Product`
where we will be adding some data for different tenants.

The `TenantUser` model will serve as the link between a database schema (tenant) and the `User`.

We will want to exclude some models from being created in every schema. The `Tenant` on save it will
generate the `schema` for a user in the database and it will automatically generate the database
models.

!!! Warning
    This is for explanation purposes, just do in the way you see fit.

```python
{!> ../docs_src/tenancy/example/models.py !}
```

This is a lot to unwrap is it? Well, that was explained [before](#models) at the top and this is just
the declaration of the models for some general purposes.

###### Generate example data

Now it is time to generate some example data and populate the tables previously created.

```python
{!> ../docs_src/tenancy/example/data.py !}
```

We now have `models` and mock data for those. You will realise that we created a `user` inside the
`shared` database (no schema associated) and one specifically inside the newly `edgy` schema.

##### Middleware

It is time to create a [middleware][middleware] that will take advantage of our new models and
tenants and **set the tenant** automatically.

The middleware will receive some headers with the tenant information and it will lookup if the
tenant exist.

!!! Danger
    Do not use this example in production, the way it is done it is not safe. A real lookup example
    would need more validations besides a direct headers check.

```python hl_lines="7 29 34"
{!> ../docs_src/tenancy/example/middleware.py !}
```

Now this is getting somewhere! As you could now see, this is where we take advantage of the
[set_tenant](#set-tenant).

In the middleware, the tenant is intercepted and all the calls in the API will now query **only**
the tenant data, which means that **there is no need for `using` or `using_with_db` anymore**.

##### API

Now it is time to simply create the API that will read the [created products](#generate-example-data)
from the database and assemble everything.

This will create an [Esmerald][esmerald] application, assemble the `routes` and add the
[middleware](#middleware) created in the previous step.

```python hl_lines="25"
{!> ../docs_src/tenancy/example/api.py !}
```

###### Query the API

If you query the API, you should have similar results to this:

```python
{!> ../docs_src/tenancy/example/query.py !}
```

The [data generated](#generate-example-data) for each schema (`shared` and `edgy`) should match
the response total returned.

##### Notes

As you could see in the previous step-by=step example, using the [set_tenant](#set-tenant) can be
extremely useful mostrly for those large scale applications where multi-tenancy is a **must** so
you can actually take advantage of this.

[registry]: ../registry.md
[schemas]: ../registry.md#schemas
[using_with_db_registry]: ../registry.md#extra
[esmerald]: https://esmerald.dev
[middleware]: https://esmerald.dev/middleware
