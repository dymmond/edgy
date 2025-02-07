# Marshalls

Imagine you need to serialize you data and adding some extra flavours on top of it. Now, imagine
that [Edgy models](./models.md) contain information that could be used but its not accessible
directly upon the moment of serialization.

Here is where the `marshalls` come into play.

The `marshalls` will simply help you adding those extra validations on the top of your existing
model and add those same extras in the serialization process or even restrict the fields being
serialized, for instance, you might not want to show all the fields.

A `marshall` is not designed to interact 100% with the database operations since that is done
by the Edgy model but it provides an interface that can also do that in case you want, the
[save method](#save).

## Marshall

This is the main class that **must** be subclassed when creating a Marshall. There is where
you declare all the extra fields and/or fields you want to serialize.

```python
from edgy.core.marshalls import Marshall
```

When declaring the `Marshall` you **must** declare a [ConfigMarshall](#configmarshall) and then
all the extras you might want to add.

In a nutshell, this is how you can use a Marshall.

```python
{!> ../docs_src/marshalls/nutshell.py !}
```

Ok, there is a lot to unwrap here but let us go step by step.

The `Marshall` has a `marshall_config` that **must be declared** specifying the `model` and `fields`.

The `fields` is a list of the **available fields** of the [model](./models.md) and it serves to specifically
specify which ones should the marshall serialize directly from the model.

Then, the `extra` and `details` are marshall `fields`, that means, the fields that are not model fields
directly but must be serialized with the extra bit of information. You can check more details about
the [Fields](#fields) later on.

When the marshall is fully declared, you can simply do this:

```python
data = {"name": "Edgy", "email": "edgy@example.com"}
marshall = UserMarshall(**data)
marshall.model_dump()
```

And the result will be:

```json
{
    "name": "Edgy",
    "email": "edgy@example.com",
    "details": "Diplay name: Edgy",
    "extra": {"address": "123 street", "post_code": "90210"},
}
```

As you can see, the `Marshall` is also a Pydantic model so you can take the full potential of it.

There are more operations and things you can do with marshalls regarding the [fields](#fields) that
you can read in the next sections.

## ConfigMarshall

To operate with the marshalls you will need to declare the `marshall_config` which is simply a
typed dictionary containing the following keys:

* **model** - The Edgy [model](./models.md) associated with the Marshall or a string `dotted.path`
pointing to the model.
* **fields** - A list of strings of the fields you want to include by default in the serialization
of the marshall.
* **exclude** - A list of strings containing the name of the fields you **don't want to** have serialized.

!!! warning
    There is a caveat though, **you can only declare `fields` or `exclude` but not both** and the `model`
    is mandatory or else an exception is raised.

=== "fields"

    ```python
    {!> ../docs_src/marshalls/fields.py !}
    ```

=== "exclude"

    ```python
    {!> ../docs_src/marshalls/exclude.py !}
    ```

The `fields` also allow the use of `__all__`. This means that you want all the fields declared in
your Edgy model.

**Example**

```python
class CustomMarshall(Marshall):
    marshall_config: ConfigMarshall = ConfigMarshall(model=User, fields=['__all__'])
```

## Fields

Here is where the things get interesting. When declaring a `Marshall` and want to add extra fields
to the serialization, you can do it by declaring two types of fields.

* [MarshallField](#marshallfield) - Used the point to a `model` field, a python `property` that is also declared
inside the Edgy model or a function.
* [MarshallMethodField](#marshallmethodfield) - Used to point to a function that is declared **inside the marshall**
and **not inside the model**.

To use the fields, you can simply import it.

```python
from edgy.core.marshalls import fields
```

All the fields have the **mandatory** attribute `field_type`. This is used to declare which type
of field should be used for automatic validation of Pydantic.

**Example**

```python
class CustomMarshall(Marshall):
    marshall_config: ConfigMarshall = ConfigMarshall(model="myapp.models.MyModel", fields=['__all__'])
    details: fields.MarshallMethodField = fields.MarshallMethodField(field_type=Dict[str, Any])
    age: fields.MarshallField = fields.MarshallField(int, source="age")
```

### MarshallField

This is the most common field you can declare in your marshall.

#### Parameters

* **field_type** - The Python type that is used by Pydantic to validate the data.
* **source** - The source of the field to be gathered from the model. It can be directly the model
field, a property or a function.

**All of the values passed in the source must come from the Edgy Model**.

**Example**

```python
{!> ../docs_src/marshalls/source.py !}
```

### MarshallMethodField

This function is used to get extra information that is provided by the `Marshall` itself.

When declaring a `MarshallMethodField` you must have the function `get_` with the corresponding
name of the field used by the `MarshallMethodField`.

When declaring the function, Edgy will automatically inject an object (instance) of the Edgy model
declared in the `marshall_config`. This instance **is not persisted in the database** unless you
specifically [save it](#save), which means, the `primary_key` will not be available until then but
the remaining object, functions, attributes and operations, are.

#### Parameters

* **field_type** - The Python type that is used by Pydantic to validate the data.

**Example**

```python
{!> ../docs_src/marshalls/method_field.py !}
```

## Including additional context
In certain scenarios, it is necessary to provide additional context to the marshall. Additional context can be provided by passing a context argument when instantiating the marshall.

**Example**

```python
class UserMarshall(Marshall):
    marshall_config: ConfigMarshall = ConfigMarshall(model=User, fields=["name", "email"],)
    additional_context: fields.MarshallMethodField = fields.MarshallMethodField(field_type=dict[str, Any])

    def get_additional_context(self, instance: edgy.Model) -> dict[str, Any]:
        return self.context


data = {"name": "Edgy", "email": "edgy@example.com"}
marshall = UserMarshall(**data, context={"foo": "bar"})
marshall.model_dump()
```

And the result will be:

```json
{
    "name": "Edgy",
    "email": "edgy@example.com",
    "additional_context": {"foo": "bar"}
}
```

## `save()`

Since the [Marshall](#marshall) is also a Pydantic base model, the same as Edgy, there may be some
times where you would like to persist the data directly using the marshall instead of using complicated
processes to make it happen.

This is also possible as Edgy made it simple for you. In the same way an Edgy model has the `save()`
so does the `marshall`. In reality, what Edgy is doing is performing that same Edgy `save()` operation
for you.

How does it work? In the same way it would work for a normal Edgy model.

### Example

Let us assume the following example.

```python
{!> ../docs_src/marshalls/method_field.py !}
```

Now, to create and save an instance of the model `User`, we simply need to:

```python
data = {
    "name": "Edgy",
    "email": "edgy@example.com",
    "language": "EN",
    "description": "Nice marshall"
}
marshall = UserMarshall(**data)
await marshall.save()
```

The marshall is smart enough to understand what fields belong to the model and what fields are
custom and specific to the marshall and persists it.

## Extra considerations

Creating a `marshall` its easy and very intuitive but there are some considerations you **must have**.

#### Model fields with `null=False`

When declaring the [ConfigMarshall](#configmarshall) `fields`, you
**must select at least the mandatory fields necessary, `null=False`, or a `MarshallFieldDefinitionError`
will be raised.

This is used to prevent any unnecessary errors from happening when the creation of the model
occurs.

#### Model validators

This remains exactly was it was before, meaning, if you want to validate the fields of the model
when creating an instance (persisted or not), that can and should be done using the normal
Pydantic `@model_validator` and `@field_validator`.
