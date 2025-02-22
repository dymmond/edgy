# Tenancy

In scenarios where you need to query data from different databases or schemas, Edgy provides robust support for multi-tenancy. This is useful when data is segregated for different users or purposes.

## What is Multi-Tenancy?

Multi-tenancy architectures commonly fall into three categories:

1.  **Shared Schemas:** All user data resides in a single schema, differentiated by unique IDs. This approach may have limitations with data privacy regulations like GDPR.
2.  **Shared Database, Different Schemas:** User data is separated into distinct schemas within the same database.
3.  **Different Databases:** User data is stored in completely separate databases.

Edgy offers three primary methods for implementing multi-tenancy:

1.  [Using](#using) in the queryset.
2.  [Using with Database](#using-with-database) in the queryset.
3.  [With Tenant](#set-tenant) for global tenant context.

Edgy also provides helpers for managing schemas, as described in the [Schemas section of the Registry documentation][schemas].

### Schema Creation

Edgy simplifies schema creation with the `create_schema` utility function:

```python
from edgy.core.tenancy.utils import create_schema
```

This function allows you to create schemas based on a given registry, enabling schema creation across different databases.

#### Parameters

* **registry:** An instance of a [Registry](../registry.md).
* **schema_name:** The name of the new schema.
* **models:** An optional dictionary mapping Edgy model names to model classes. If not provided, tables are generated from the registry's models.
* **if_not_exists:** If `True`, the schema is created only if it doesn't exist. Defaults to `False`.
* **should_create_tables:** If `True`, tables are created within the new schema. Defaults to `False`.

**Example:**

```python
import edgy
from edgy.core.tenancy.utils import create_schema

database = edgy.Database("sqlite:///db.sqlite")
registry = edgy.Registry(database=database)

# Create the schema
await create_schema(
    registry=registry,
    schema_name="edgy",
    if_not_exists=True,
    should_create_tables=True
)
```

### Using

The `using` method allows you to specify a schema for a specific query, overriding the default schema set in the registry.

**Parameters:**

* **schema:** A string representing the schema name.

**Syntax:**

```python
<Model>.query.using(schema=<SCHEMA-NAME>).all()
```

This method can be used with any query type, not just `all()`.

**Example:**

Consider two schemas, `default` and `other`, each containing a `User` table.

```python
{!> ../docs_src/tenancy/using/schemas.py !}
```

**Querying the default schema:**

```python
User.query.all()
```

**Querying the `main` schema:**

```python
User.query.using(schema='main').all()
```

### Using with Database

The `using_with_db` method allows you to query a schema in a different database.

{!> ../docs_src/shared/extra.md !}

### Set Tenant

The `with_tenant` context manager sets a global tenant context for your application, ensuring all queries within the context target the specified tenant's data.

```python
from edgy.core.db import with_tenant
```

!!! Tip
    Use `with_tenant` in middleware or interceptors to set the tenant context before API requests.

!!! Warning
    The `set_tenant` function is deprecated and should not be used.

#### Practical Case

Let's illustrate `with_tenant` with an Esmerald application example.

**Building:**

* [Models](#models): Define models for tenants, users, and products.
* [Middleware](#middleware): Intercept requests and set the tenant context.
* [API](#api): Create an API to retrieve tenant-specific data.

##### Models

Define models to represent tenants, users, and products:

```python
{!> ../docs_src/tenancy/example/models.py !}
```

The `TenantUser` model links database schemas to users.

##### Generate Example Data

Populate the tables with example data:

```python
{!> ../docs_src/tenancy/example/data.py !}
```

##### Middleware

Create middleware to intercept requests and set the tenant context:

```python hl_lines="7 29 34"
{!> ../docs_src/tenancy/example/middleware.py !}
```

The `with_tenant` context manager sets the tenant context for all API calls.

##### API

Create an Esmerald API to retrieve product data:

```python hl_lines="25"
{!> ../docs_src/tenancy/example/api.py !}
```

##### Query the API

Querying the API should return data corresponding to the specified tenant:

```python
{!> ../docs_src/tenancy/example/query.py !}
```

##### Tenant Only Models

To prevent models from being created in the non-tenant schema, set `register_default` to `False` in the model's Meta.

##### Notes

The `with_tenant` context manager is particularly useful for large-scale multi-tenant applications, simplifying tenant data management.

[registry]: ../registry.md
[schemas]: ../registry.md#schemas
[using_with_db_registry]: ../registry.md#extra
[esmerald]: [https://esmerald.dev](https://esmerald.dev)
[middleware]: [https://esmerald.dev/middleware](https://esmerald.dev/middleware)
