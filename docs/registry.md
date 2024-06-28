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

* **database** - An instance of `edgy.core.db.Database` object.

!!! Warning
    Using the `Database` from the `databases` package will raise an assertation error. You must
    use the `edgy.Database` object instead.

* **schema** - The schema to connect to. This can be very useful for multi-tenancy applications if
you want to specify a specific schema or simply if you just want to connect to a different schema
that is not the default.

    ```python
    from edgy import Registry

    registry = Registry(database=..., schema="custom-schema")
    ```

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

**init_models(self, *, init_column_mappers=True, init_class_attrs=True)** - Fully initializes models and metas. Single sub-components can be excluded.

**invalidate_models(self, *, clear_class_attrs=True)** - Invalidates metas and removes cached class attributes. Single sub-components can be excluded.


Model class attributes `class_attrs` which are cleared or set are `table`, `pknames`, `pkcolumns`.

`init_column_mappers` initializes the `columns_to_field` via its `init()` method. This initializes the mappers `columns_to_field`, `field_to_columns` and `field_to_column_names`.

`db_schema` internally calls also `invalidate_models()` to remove table references.
