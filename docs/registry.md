# Registry

When working with the **Edgy** ORM, the **Registry** object is essential for specifying the database connection.

Think of the registry as a mapping between your models and the database where data will be stored.

It's a simple yet effective object with a crucial role. The registry is also used for generating migrations with Alembic.

```python hl_lines="19"
{!> ../docs_src/registry/model.py !}
```

## Parameters

* **database**: An instance of `edgy.core.db.Database` or a connection string. When using a string, unparsed keyword arguments are passed to the created `Database` object.

    !!! Warning
        Using `Database` from the `databases` package raises an assertion error. Edgy uses the `databasez` fork, and it's recommended to use a string, `edgy.Database`, or `edgy.testclient.TestClient`. Future versions may add more Edgy-specific functionality.

* **schema**: The schema to connect to. Useful for multi-tenancy applications or connecting to non-default schemas.

    ```python
    from edgy import Registry

    registry = Registry(database=..., schema="custom-schema")
    ```

* **extra**: A dictionary of extra connections (same types as the `database` argument) managed by the registry (connecting/disconnecting). They can be arbitrary connected databases. It ensures they're not torn down while the registry is connected.

* **with_content_type**: A boolean or a custom abstract `ContentType` prototype. Enables `ContentTypes` and saves the used type as the `content_type` attribute.

## Connecting/Disconnecting

Registries support the asynchronous context manager protocol and the ASGI lifespan protocol. This ensures all databases specified in `database` or `extra` are properly referenced and dereferenced (triggering initialization and teardown when the reference count reaches 0). This allows safe use of databases across different contexts.

## Accessing ContentType

The registry has a `content_type` attribute for accessing the active `ContentType`.

## Direct Database Access

The registry has a `database` attribute for the main database and an `extra` dictionary for extra databases. Retrieving the `Database` object from the registry is safer and ensures you get the correct instance.

## Custom Registry

You can create custom registries by subclassing the `Registry` class.

```python hl_lines="15 29"
{!> ../docs_src/registry/custom_registry.py !}
```

## Multiple Registries

You can work with multiple databases across different functionalities using multiple registries with [Meta](./models.md#the-meta-class) combinations.

```python hl_lines="26 33"
{!> ../docs_src/registry/multiple.py !}
```

## Schemas

Edgy supports database schema operations like [creating schemas](#create-schema) and [dropping schemas](#drop-schema).

This is useful for multi-tenancy applications or custom schema management.

### Create Schema

Creates database schemas.

**Parameters**:

* **schema**: String name of the schema.
* **if_not_exists**: Flag to create if the schema doesn't exist.
* **databases**: String or `None` for the main database. You can create schemas on databases in `extra` too.

    <sup>Default: `False`</sup>

```python hl_lines="11"
{!> ../docs_src/registry/create_schema.py !}
```

Create a schema named `edgy`.

```python
await create_schema("edgy")
```

This creates the `edgy` schema if it doesn't exist. If `if_not_exists` is `False` and the schema exists, it raises `edgy.exceptions.SchemaError`.

### Drop Schema

Drops database schemas.

!!! Warning
    Use `drop_schema` with caution, as it's irreversible. Avoid deleting the `default` schema.

**Parameters**:

* **schema**: String name of the schema.
* **cascade**: Flag for cascade delete.

    <sup>Default: `False`</sup>

* **if_exists**: Flag to drop if the schema exists.

    <sup>Default: `False`</sup>
* **databases**: String or None for main database. You can drop schemes on databases in extra too.

```python hl_lines="11"
{!> ../docs_src/registry/drop_schema.py !}
```

Drop a schema named `edgy`.

```python
await drop_schema("edgy")
```

This drops the `edgy` schema if it exists. If `if_exists` is `False` and the schema doesn't exist, it raises `edgy.exceptions.SchemaError`.

### Get Default Schema Name

Helper function to get the default schema name for the database (e.g., `public` for Postgres, `dbo` for MSSQL).

```python hl_lines="11"
{!> ../docs_src/registry/default_schema.py !}
```

## Extra

{!> ../docs_src/shared/extra.md !}

## Laziness

For advanced users who want to control the laziness of `meta` objects.

Registry objects have helper functions to undo laziness (for optimizations or static environments):

* **init_models(self, \*, init_column_mappers=True, init_class_attrs=True)**: Fully initializes models and metas. Exclude elements by setting keyword arguments to `False`.
* **invalidate_models(self, \*, clear_class_attrs=True)**: Invalidates metas and removes cached class attributes. Exclude sub-components from invalidation.

Model class attributes (`table`, `pknames`, `pkcolumns`, `proxy_model`, `table_schema`) are cleared or initialized.

Manual initialization is usually unnecessary and can cause performance penalties.

`init_column_mappers` initializes `columns_to_field` via its `init()` method, which can be expensive for large models.

## Callbacks

Use callbacks to modify models or specific models when they're available.

Register callbacks with a model name or `None` (for all models). When a model class is added, the callback is executed with the model class as a parameter.

Callbacks can be permanent or one-time (triggered by the first match). If a model is already registered, it's passed to the callback.

Use `register_callback(model_or_name, callback, one_time)`.

Generally, use `one_time=True` for model-specific callbacks and `one_time=False` for model-unspecific callbacks.

If `one_time` is not provided, the logic mentioned above is applied.
