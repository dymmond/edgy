# Marshalls in Edgy

Marshalls in Edgy provide a powerful mechanism for serializing data and adding extra layers of customization. They allow you to augment Edgy models with additional information that might not be directly accessible during serialization.

Essentially, marshalls facilitate adding validations on top of existing models and customizing the serialization process, including restricting which fields are serialized. While not primarily designed for direct database interaction, marshalls offer an interface to perform such operations if needed, through the `save()` method.

## Marshall Class

The `Marshall` class is the base class that **must** be subclassed when creating a marshall. It's where you define extra fields and specify which fields to serialize.

```python
from edgy.core.marshalls import Marshall
```

When declaring a `Marshall`, you **must** define a [ConfigMarshall](#configmarshall) and then add any extra fields you want.

Here's a basic example of how to use a marshall:

```python
{!> ../docs_src/marshalls/nutshell.py !}
```

Let's break this down step by step.

The `Marshall` has a `marshall_config` attribute that **must be declared**, specifying the `model` and `fields`.

The `fields` list contains the names of the [model](./models.md) fields that should be serialized directly from the model.

The `extra` and `details` fields are marshall-specific fields, meaning they are not directly from the model but are included in the serialization. You can find more details about these [Fields](#fields) later in this document.

Once the marshall is defined, you can use it like this:

```python
data = {"name": "Edgy", "email": "edgy@example.com"}
marshall = UserMarshall(**data)
marshall.model_dump()
```

The result will be:

```json
{
    "name": "Edgy",
    "email": "edgy@example.com",
    "details": "Diplay name: Edgy",
    "extra": {"address": "123 street", "post_code": "90210"},
}
```

As you can see, `Marshall` is also a Pydantic model, allowing you to leverage its full potential.

There are more operations and customizations you can perform with marshalls, particularly regarding [fields](#fields), which are covered in the following sections.

## ConfigMarshall

To work with marshalls, you need to declare a `marshall_config`, which is a typed dictionary containing the following keys:

* **model:** The Edgy [model](./models.md) associated with the marshall, or a string `dotted.path` pointing to the model.
* **fields:** A list of strings representing the fields to include in the marshall's serialization.
* **exclude:** A list of strings representing the fields to exclude from the marshall's serialization.
* **primary_key_read_only** Make primary key fields read-only.
* **exclude_autoincrement** Post-filter autoincrement fields.
* **exclude_read_only** Post-filter read-only fields. Removes also read-only made primary-keys.

!!! warning
    **You can only declare either `fields` or `exclude`, but not both.** The `model` is mandatory, or an exception will be raised.

=== "fields"

    ```python
    {!> ../docs_src/marshalls/fields.py !}
    ```

=== "exclude"

    ```python
    {!> ../docs_src/marshalls/exclude.py !}
    ```

The `fields` list also supports the use of `__all__`, which includes all fields declared in your Edgy model.

**Example:**

```python
class CustomMarshall(Marshall):
    marshall_config: ConfigMarshall = ConfigMarshall(model=User, fields=['__all__'])
```

## Fields

This is where things get interesting. When declaring a `Marshall` and adding extra fields to the serialization, you can use two types of fields:

* [MarshallField](#marshallfield): Used to reference a model field, a Python `property` defined in the Edgy model, or a function.
* [MarshallMethodField](#marshallmethodfield): Used to reference a function defined **within the marshall**, not the model.

To use these fields, import them:

```python
from edgy.core.marshalls import fields
```

All fields have a **mandatory** attribute `field_type`, which specifies the Python type used by Pydantic for validation.

**Example:**

```python
class CustomMarshall(Marshall):
    marshall_config: ConfigMarshall = ConfigMarshall(model="myapp.models.MyModel", fields=['__all__'])
    details: fields.MarshallMethodField = fields.MarshallMethodField(field_type=Dict[str, Any])
    age: fields.MarshallField = fields.MarshallField(int, source="age")
```

### MarshallField

This is the most common field type used in marshalls.

#### Parameters

* **field_type:** The Python type used by Pydantic for data validation.
* **source:** The source of the field, which can be a model field, a property, or a function.

**All values passed in the source must come from the Edgy Model.**

**Example:**

```python
{!> ../docs_src/marshalls/source.py !}
```

### MarshallMethodField

This field type is used to retrieve extra information provided by the `Marshall` itself.

When declaring a `MarshallMethodField`, you must define a function named `get_` followed by the field name.

Edgy automatically injects an instance of the Edgy model declared in `marshall_config` into this function. This instance **is not persisted in the database** unless you explicitly [save it](#save-method). Therefore, the `primary_key` will not be available until then, but other object attributes and operations are.

#### Parameters

* **field_type:** The Python type used by Pydantic for data validation.

**Example:**

```python
{!> ../docs_src/marshalls/method_field.py !}
```

## Including Additional Context

In some cases, you might need to provide extra context to a marshall. You can do this by passing a `context` argument when instantiating the marshall.

**Example:**

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

Result:

```json
{
    "name": "Edgy",
    "email": "edgy@example.com",
    "additional_context": {"foo": "bar"}
}
```

## Interopability with plain pydantic

You can also add plain pydantic fields. They are without any features and can be used for different signalling.

## Partial Marshalls.

Sometimes you want to use marshalls for only updates of some attributes.
You can just define the attributes you want to update and assign the instance later.
If the fields you ignore are required, it is an error to not assign the instance and call save.

``` python
class User(edgy.Model):
    # this is required
    name: str = edgy.CharField(max_length=100, primary_key=True)
    email: str = edgy.EmailField(max_length=100, null=True)

    class Meta:
        registry = models

class EmailUpdateMarshall(Marshall):
    marshall_config = ConfigMarshall(model=User, fields=["email"])

@post("/update_email/{id}")
async def update_email(id: int, data: EmailUpdateMarshall) -> EmailUpdateMarshall:
    data.instance = await User.query.get(id=id)
    await data.save()
    return data

## the following would crash when saving or accessing instance, because "name" is required

# @post("/create_user")
# async def create_user(id: int, data: EmailUpdateMarshall) -> EmailUpdateMarshall:
#     await data.save()
#     return data
```

## `save()` Method

Since `Marshall` is a Pydantic base model, similar to Edgy models, you can persist data directly using the marshall.

Edgy provides a `save()` method for marshalls that forwards to the `save()` method of Edgy models. It doesn't take any parameters.

### Example

Using the `UserMarshall` from the previous example:

```python
{!> ../docs_src/marshalls/method_field.py !}
```

To create and save a `User` instance:

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

The marshall intelligently distinguishes between model fields and marshall-specific fields and persists the model fields.

## Extra Considerations

Creating marshalls is straightforward, but keep these points in mind:

#### Model Fields with `null=False`

When declaring `ConfigMarshall` `fields`, you **must select at least the mandatory fields (`null=False`)**, or a `MarshallFieldDefinitionError` will be raised.

This prevents errors during model creation.

#### Model Validators

Model validators (using `@model_validator` and `@field_validator`) work as expected. You can use them to validate model fields during instance creation.
