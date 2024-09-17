# Registry

When using the **Edgy** ORM, you must use the **Registry** object to tell exactly where the
database is going to be.

Imagine the registry as a mapping between your models and the database where is going to be written.

And is just that, nothing else and very simple but effective object.

The registry is also the object that you might want to use when generating migrations using
Alembic.

```python hl_lines="19"
{!> ../docs_src/registry/model.py !}
```

## Parameters

* **database** - An instance of `edgy.core.db.Database` object or a string. When providing a string all unparsed keyword arguments are passed the created Database object.

!!! Warning
    Using the `Database` from the `databases` package will raise an assertation error. Edgy is build on the
    fork `databasez` and it is strongly recommended to use a string, `edgy.Database` or `edgy.testclient.TestClient` instead.
    In future we may add more edgy specific functionality.

* **schema** - The schema to connect to. This can be very useful for multi-tenancy applications if
you want to specify a specific schema or simply if you just want to connect to a different schema
that is not the default.

    ```python
    from edgy import Registry

    registry = Registry(database=..., schema="custom-schema")
    ```

* **extra** - A dictionary with extra connections (same types like the database argument) which are managed by the registry too (connecting/disconnecting). They may can be arbitary connected databases. It is just ensured that they are not tore down during the registry is connected.

* **with_content_type** - Either a bool or a custom abstract ContentType prototype. This enables ContentTypes and saves the actual used type as attribute: `content_type`


## Connecting/Disconnecting

Registries support the async contextmanager protocol as well as the ASGI lifespan protocol.
This way all databases specified as database or extra are properly referenced and dereferenced
(triggering the initialization and tear down routines when reaching 0).
This way all of the dbs can be safely used no matter if they are used in different contexts.

## Accessing the ContentType

The registry has an attribute `content_type` for accessing the active ContentType.

## Accessing directly the databases

The registry has an attribute `database` for the main database and a dictionary `extra` containing the active extra
databases.
It is not necessary anymore to keep the Database object available, it can be simply retrieved from the db which is by the way
safer. This way it is ensured you get the right one.

## Custom registry

Can you have your own custom Registry? Yes, of course! You simply need to subclass the `Registry`
class and continue from there like any other python class.

```python hl_lines="15 29"
{!> ../docs_src/registry/custom_registry.py !}
```

## Multiple registries

Sometimes you might want to work with multiple databases across different functionalities and
that is also possible thanks to the registry with [Meta](./models.md#the-meta-class) combination.

```python hl_lines="26 33"
{!> ../docs_src/registry/multiple.py !}
```

## Schemas

This is another great supported feature from Edgy. This allows you to manipulate database schema
operations like [creating schemas](#create-schema) or [dropping schemas](#drop-schema).

This can be particulary useful if you want to create a [multi-tenancy](./tenancy/edgy.md) application
and you need to generate schemas for your own purposes.

### Create schema

As the name suggests, it is the functionality that allows you to create database schemas.

**Parameters**:

* **schema** - String name of the schema.
* **if_not_exists** - Flag indicating if should create if not exists.
* **databases** - String or None for main database. You can create schemes on databases in extra too.

    <sup>Default: `False`</sup>

```python hl_lines="11"
{!> ../docs_src/registry/create_schema.py !}
```

Create a schema called `edgy`.

```python
await create_schema("edgy")
```

This will make sure it will create a new schema `edgy` if it does not exist. If the `if_not_exists`
is `False` and the schema already exists, it will raise a `edgy.exceptions.SchemaError`.

### Drop schema

As name also suggests, it is the opposite of [create_schema](#create-schema) and instead of creating
it will drop it from the database.

!!! Warning
    You need to be very careful when using the `drop_schema` as the consequences are irreversible
    and not only you don't want to remove the wrong schema but also you don't want to delete the
    `default` schema as well. Use it with caution.

**Parameters**:

* **schema** - String name of the schema.
* **cascade** - Flag indicating if should do `cascade` delete.
*
    <sup>Default: `False`</sup>

* **if_exists** - Flag indicating if should create if not exists.

    <sup>Default: `False`</sup>
* **databases** - String or None for main database. You can drop schemes on databases in extra too.

```python hl_lines="11"
{!> ../docs_src/registry/drop_schema.py !}
```

Drop a schema called `edgy`

```python
await drop_schema("edgy")
```

This will make sure it will drop a schema `edgy` if exists. If the `if_exists`
is `False` and the schema does not exist, it will raise a `edgy.exceptions.SchemaError`.

### Get default schema name

This is just a helper. Each database has its own ***default*** schema name, for example,
Postgres calls it `public` and MSSQLServer calls it `dbo`.

This is just an helper in case you need to know the default schema name for any needed purpose of
your application.

```python hl_lines="11"
{!> ../docs_src/registry/default_schema.py !}
```

## Extra

{!> ../docs_src/shared/extra.md !}


## Lazyness

Note: this is something for really advanced users who want to control the lazyness of `meta` objects. Skip if you just want use the framework
and don't want to micro-optimize your code.

Registry objects have two helper functions which can undo the lazyness (for optimizations or in case of an environment which requires everything being static after init.):

**init_models(self, *, init_column_mappers=True, init_class_attrs=True)** - Fully initializes models and metas. Some elements can be excluded from initialization by providing False to the keyword argument.

**invalidate_models(self, *, clear_class_attrs=True)** - Invalidates metas and removes cached class attributes. Single sub-components can be excluded from inval.


Model class attributes `class_attrs` which are cleared or initialized are `table`, `pknames`, `pkcolumns`, `proxy_model`, `table_schema` (only cleared).

However in most cases it won't be necessary to initialize them manually and causes performance penalties.

`init_column_mappers` initializes the `columns_to_field` via its `init()` method. This initializes the mappers `columns_to_field`, `field_to_columns` and `field_to_column_names`. This can be expensive for large models.


## Callbacks

Sometimes you want to modify all models or a specific model but aren't sure if they are available yet.
Here we have now the callbacks in a registry.
You register a callback with a model name or None (for all models) and whenever a model class of the criteria is added the callback with
the model class as parameter is executed.
Callbacks can be registered permanent or one time (the first match triggers them). If a model is already registered it is passed to the callback too.
The method is called `register_callback(model_or_name, callback, one_time)`.

Generally you use `one_time=True` for model specific callbacks and `one_time=False` for model unspecific callbacks.

If `one_time` is not provided, the logic mentioned above is applied.
