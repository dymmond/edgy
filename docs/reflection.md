# Reflection

When working for a big project, sometimes new, sometimes legacy, you might face cases where there
is already an existing database with tables and views and you simply would like to reflect them
into your code by representation without the need of creating new ones.

This is where Edgy reflection comes in.

## What is reflection

Reflection means the opposite of creating the [models](./models.md), meaning, reading
**tables and views** from an existing back into your code.

Let us see an example.

Imagine you have the following table generated into the database.

```python
{!> ../docs_src/reflection/model.py !}
```

This will create a table called `users` in the database as expected.

!!! Note
    We use the previous example to generate a table for explanation purposes. If you already
    have tables in a given db, you don't need this.

Now you want to reflect the existing table `users` from the database into your models (code).

```python hl_lines="8"
{!> ../docs_src/reflection/reflect.py !}
```

What is happening is:

* The `ReflectModel` is going to the database.
* Reads the existing tables.
* Verifies if there is any `users` table name.
* Converts the `users` fields into Edgy model fields.

### Note

**ReflectModel works with database tables AND database views**. That is right, you can use the
model reflect to reflect existing database tables and database views from any existing database.

## ReflectModel

The reflect model is very similar to `Model` from [models](./models.md) but with a main difference
that won't generate any migrations.

```python
from edgy import ReflectModel
```

The same operations of inserting, deleting, updating and creating are still valid and working
as per normal behaviour.

**Parameters**

As per normal model, it is required the `Meta` class with two parameters.

* **registry** - The [registry](./registry.md) instance for where the model will be generated. This
field is **mandatory** and it will raise an `ImproperlyConfigured` error if no registry is found.

* **tablename** - The name of the table or view to be reflected from the database, **not the class name**.

    <sup>Default: `name of class pluralised`<sup>

Example:

```python hl_lines="13 14"
{!> ../docs_src/reflection/reflect.py !}
```

## Fields

The fields should be declared as per normal [fields](./fields.md) that represents the columns from
the reflected database table or view.

Example:

```python hl_lines="9 10"
{!> ../docs_src/reflection/reflect.py !}
```

### The difference from the models

When reflecting a model or a view from an existing database, usually you want to reflect the
existing fields from it but sometimes in your code, you simply want **only a few fields** reflected
and not all of them for your own reasons.

Edgy `ReflectModel` does this for you.

Let us see an example:

Consider this table as already been created in a database somewhere with the following structure.

```python
{!> ../docs_src/reflection/reflect/model.py !}
```

!!! Check
    For this example, we use a pythonic representation of a table in a database instead of a SQL as
    it looks easier to understand what is what in this context.

Now imagine somewhere in another application you want to reflect the existing `users` table
(above) but you only want a few fields and not all of them.

Your reflect model would look like this:

```python hl_lines="9-11"
{!> ../docs_src/reflection/reflect/reflect.py !}
```

Meaning, although you migh have legacy tables you still want to use you might also want to use
only a few necessary fields for your operations and this is what `ReflectModel` allows you to
achieve.

## Operations

What about the database operations like the CRUD? Are they still possible with `ReflectModel`?

The answer is **yes**.

With `ReflectModel` you can still perform the normal operations as you would do with
[models](./models.md) anyway.

Remember the [difference from the models](#the-difference-from-the-models)? Well here is another
thing. The `ReflectModel` will only perform operations on the declared fields of the
same `ReflectModel`.

In other words, if you want to update a field that is the table being reflected but **not in**
the `ReflectModel` declaration, **the operation on that field will not happen**.

!!! Warning
    If you are reflecting SQL views, you probably will not be able to write (create, update...) as
    the SQL view has that same limitation.
