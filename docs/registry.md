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
you want to specify a specific schema or simlpy if you just want to connect to a different schema
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
