# Reflection

In large projects, especially those with legacy databases, you often need to represent existing database tables and views in your code without recreating them. Edgy's reflection feature provides a solution for this.

## What is Reflection?

Reflection involves reading existing database **tables and views** and representing them as models in your code, effectively mirroring their structure.

Let's illustrate with an example.

Suppose you have a `users` table in your database, created using the following Edgy model:

```python
{!> ../docs_src/reflection/model.py !}
```

This code snippet creates a `users` table in the database.

!!! Note
    This example is for demonstration purposes. If you already have tables in your database, you don't need to create them again.

Now, you want to reflect this existing `users` table into your Edgy models:

```python hl_lines="8"
{!> ../docs_src/reflection/reflect.py !}
```

Here's what happens:

* `ReflectModel` connects to the database.
* It reads the existing tables.
* It identifies the `users` table.
* It converts the `users` table columns into Edgy model fields.

### Key Feature

`ReflectModel` works with both **database tables and views**. This allows you to represent any existing data structure in your code.

## ReflectModel: Representing Existing Data

`ReflectModel` is similar to Edgy's `Model` but it does not generate migrations.

```python
from edgy import ReflectModel
```

It supports standard database operations like inserting, deleting, updating, and creating records.

**Parameters:**

* **`Meta.registry`**: The [registry](../registry.md) instance. This is **mandatory**.
* **`Meta.tablename`**: The name of the table or view to reflect. Defaults to the pluralized class name.

Example:

```python hl_lines="13 14"
{!> ../docs_src/reflection/reflect.py !}
```

## Fields: Mapping Database Columns

Fields in `ReflectModel` are declared like regular [fields](../fields/index.md), representing the columns of the reflected table or view.

Example:

```python hl_lines="9 10"
{!> ../docs_src/reflection/reflect.py !}
```

### Key Difference from Regular Models

Unlike regular Edgy models, `ReflectModel` allows you to specify only the fields you need, rather than requiring all fields from the database table or view.

Example:

Suppose you have a `users` table with the following structure:

```python
{!> ../docs_src/reflection/reflect/model.py !}
```

And you want to reflect only a few fields:

```python hl_lines="9-11"
{!> ../docs_src/reflection/reflect/reflect.py !}
```

This flexibility allows you to work with only the necessary fields, simplifying your code.

## Operations: CRUD Functionality

`ReflectModel` supports standard CRUD operations, just like regular Edgy models.

However, it only performs operations on the fields declared in the `ReflectModel`. If you attempt to update a field that is not declared in the `ReflectModel`, the operation will not occur.

!!! Warning
    SQL views may have limitations on write operations (create, update, etc.).

## Reflection Outside of Defaults

To reflect tables from a different database or schema, set `__using_schema__` and `database` after model creation.

```python
import edgy

registry = edgy.Registry(...)

class AdvancedReflected(edgy.ReflectModel):
    __using_schema__ = "foo"
    a = edgy.CharField(max_length=40)

    class Meta:
        registry = registry

AdvancedReflected.database = otherdb
AdvancedReflected.__using_schema__ = "foo"
```

This technique is used by `AutoReflectModel` for automatic reflection.
