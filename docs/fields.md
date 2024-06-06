# Fields

Fields are what is used within model declaration (data types) and defines wich types are going to
be generated in the SQL database when generated.

## Data types

As **Edgy** is a new approach on the top of Encode ORM, the following keyword arguments are
supported in **all field types**.

!!! Check
    The data types are also very familiar for those with experience with Django model fields.

* **primary_key** - A boolean. Determine if a column is primary key.
Check the [primary_key](./models.md#restrictions-with-primary-keys) restrictions with Edgy.
* **exclude** - An bool indicating if the field is included in model_dump
* **default** - A value or a callable (function).
* **index** - A boolean. Determine if a database index should be created.
* **skip_absorption_check** - A boolean. Default False. Dangerous option! By default when defining a CompositeField with embedded fields and the `absorb_existing_fields` option it is checked that the field type of the absorbed field is compatible with the field type of the embedded field. This option skips the check.
* **unique** - A boolean. Determine if a unique constraint should be created for the field.
Check the [unique_together](./models.md#unique-together) for more details.

All the fields are required unless on the the following is set:

* **null** - A boolean. Determine if a column allows null.

    <sup>Set default to `None`</sup>

* **server_default** - instance, str, Unicode or a SQLAlchemy `sqlalchemy.sql.expression.text`
construct representing the DDL DEFAULT value for the column.
* **comment** - A comment to be added with the field in the SQL database.
* **secret** - A special attribute that allows to call the [exclude_secrets](./queries/secrets.md#exclude-secrets) and avoid
accidental leakage of sensitive data.

## Available fields

All the values you can pass in any Pydantic [Field](https://docs.pydantic.dev/latest/concepts/fields/)
are also 100% allowed within Mongoz fields.

### Importing fields

You have a few ways of doing this and those are the following:

```python
import edgy
```

From `edgy` you can access all the available fields.

```python
from edgy.core.db import fields
```

From `fields` you should be able to access the fields directly.

```python
from edgy.core.db.fields import BigIntegerField
```

You can import directly the desired field.

All the fields have specific parameters beisdes the ones [mentioned in data types](#data-types).

#### BigIntegerField

```python
import edgy


class MyModel(edgy.Model):
    big_number: int = edgy.BigIntegerField(default=0)
    another_big_number: int = edgy.BigIntegerField(minimum=10)
    ...

```

This field is used as a default field for the `id` of a model.

##### Parameters:

* **minimum** - An integer, float or decimal indicating the minimum.
* **maximum** - An integer, float or decimal indicating the maximum.
* **max_digits** - Maximum digits allowed.
* **multiple_of** - An integer, float or decimal indicating the multiple of.
* **decimal_places** - The total decimal places.

#### IntegerField

```python
import edgy


class MyModel(edgy.Model):
    a_number: int = edgy.IntegerField(default=0)
    another_number: int = edgy.IntegerField(minimum=10)
    ...

```

##### Parameters:

* **minimum** - An integer, float or decimal indicating the minimum.
* **maximum** - An integer, float or decimal indicating the maximum.
* **max_digits** - Maximum digits allowed.
* **multiple_of** - An integer, float or decimal indicating the multiple of.
* **decimal_places** - The total decimal places.

#### BooleanField

```python
import edgy


class MyModel(edgy.Model):
    is_active: bool = edgy.BooleanField(default=True)
    is_completed: bool = edgy.BooleanField(default=False)
    ...

```

#### CharField

```python
import edgy


class MyModel(edgy.Model):
    description: str = edgy.CharField(max_length=255)
    title: str = edgy.CharField(max_length=50, min_length=200)
    ...

```

##### Parameters:

* **max_length** - An integer indicating the total length of string.
* **min_length** - An integer indicating the minimum length of string.

#### ChoiceField

```python
from enum import Enum
import edgy

class Status(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class MyModel(edgy.Model):
    status: Status = edgy.ChoiceField(choices=Status, default=Status.ACTIVE)
    ...

```

##### Parameters

* **choices** - An enum containing the choices for the field.

#### CompositeField

The **CompositeField** is a little bit different from the normal fields. It takes a parameter `inner_fields` and distributes write or read access to the fields
referenced in `inner_fields`. It hasn't currently all field parameters. Especially not the server parameters.
For distributing the field parameters it uses the `Descriptor Protocol` for reading and `to_model` for writing.

Optionally a pydantic model can be provided via the **model** argument.

**CompositeField** defines no columns as it is a meta field.

Note there is also **BaseCompositeField**. It can be used for implementing own **CompositeField**-like fields.


```python
import edgy


class MyModel(edgy.Model):
    email: str = edgy.EmailField(max_length=60, null=True)
    sent: datetime.datetime = edgy.DateTimeField(, null=True)
    composite: edgy.CompositeField = edgy.CompositeField(inner_fields=["email", "sent"])
    ...

class MyModel(edgy.Model):
    email: str = edgy.EmailField(max_length=60, null=True, read_only=True)
    sent: datetime.datetime = edgy.DateTimeField(, null=True, read_only=True)
    composite = edgy.CompositeField(inner_fields=["email", "sent"])
    ...

obj = MyModel()
obj.composite = {"email": "foobar@example.com", "sent": datetime.datetime.now()}

# retrieve as dict
ddict = obj.composite
```

The contained fields are serialized like normal fields. So if this is not wanted,
the fields need the exclude attribute/parameter set

##### Parameters

* **inner_fields** - Required. A sequence containing the external field names mixed with embedded field definitions (name, Field) tuples.
* **unsafe_json_serialization** - Default False. Normally when serializing in json mode, CompositeFields are ignored when they don't have a pydantic model set. This option includes such CompositeFields in the dump.
* **absorb_existing_fields** - Default False. Don't fail if fields speficied with (name, Field) tuples already exists. Treat them as internal fields. The existing fields are checked if they are a subclass of the Field or have the attribute `skip_absorption_check` set
* **model** - Default None (not set).Return a pydantic model instead of a dict
* **prefix_embedded** - Default "". Prefix the field names of embedded fields (not references to external fields). Useful for implementing embeddables

Note: embedded fields are deepcopied. This way it is safe to provide the same inner_fields object to multiple CompositeFields


Note: there is a special parameter for model: `ConditionalRedirect`.
It changes the behaviour of CompositeField in this way:

- `inner_fields` with 1 element: Reads and writes are redirected to this field. When setting a dict or pydantic BaseModel the value is tried to be extracted like in the normal mode. Otherwise the logic of the single field is used. When returning only the value of the single field is returned
- `inner_fields` with >1 element: normal behavior. Dicts are returned


##### Inheritance

CompositeFields are evaluated in non-abstract models. When overwritten by another field and the evaluation didn't take place yet no fields are generated.

When overwritten after evaluation the fields are still lingering around.

You can also overwrite from CompositeField generated fields in subclasses regardless if the CompositeField used absorb_existing_fields inside.

You may want to use **ExcludeField** to remove fields.

#### DateField

```python
import datetime
import edgy


class MyModel(edgy.Model):
    created_at: datetime.date = edgy.DateField(default=datetime.date.today)
    ...

```

##### Parameters

* **auto_now** - A boolean indicating the `auto_now` enabled. Useful for auto updates.
* **auto_now_add** - A boolean indicating the `auto_now_add` enabled. This will ensure that it is
only added once.

#### DateTimeField

```python
import datetime
import edgy


class MyModel(edgy.Model):
    created_at: datetime.datetime = edgy.DateTimeField(default=datetime.datetime.now)
    ...

```

##### Parameters

* **auto_now** - A boolean indicating the `auto_now` enabled. Useful for auto updates.
* **auto_now_add** - A boolean indicating the `auto_now_add` enabled. This will ensure that it is
only added once.

#### DecimalField

```python
import decimal
import edgy

class MyModel(edgy.Model):
    price: decimal.Decimal = edgy.DecimalField(max_digits=5, decimal_places=2, null=True)
    ...

```

##### Parameters

* **minimum** - An integer indicating the minimum.
* **maximum** - An integer indicating the maximum.
* **max_digits** - An integer indicating the total maximum digits.
* **decimal_places** - An integer indicating the total decimal places.
* **multiple_of** - An integer, float or decimal indicating the multiple of.

#### EmailField

```python
import edgy


class MyModel(edgy.Model):
    email: str = edgy.EmailField(max_length=60, null=True)
    ...

```

Derives from the same as [CharField](#charfield) and validates the email value.

#### ExcludeField

Remove inherited fields by masking them from the model.
This way a field can be removed in subclasses.

ExcludeField is a stub field and can be overwritten itself in case a Model wants to readd the field.

When given an argument in the constructor the argument is silently ignored.
When trying to set/access the attribute on a model instance, an AttributeError is raised.

```python
import edgy


class AbstractModel(edgy.Model):
    email: str = edgy.EmailField(max_length=60, null=True)
    price: float = edgy.FloatField(null=True)

    class Meta:
        abstract = True

class ConcreteModel(AbstractModel):
    email: Type[None] = edgy.ExcludeField()

# works
obj = ConcreteModel(email="foo@example.com", price=1.5)
# fails with AttributeError
variable = obj.email
obj.email = "foo@example.com"
```

#### FloatField

```python
import edgy


class MyModel(edgy.Model):
    price: float = edgy.FloatField(null=True)
    ...

```

Derives from the same as [IntergerField](#integerfield) and validates the decimal float.

#### ForeignKey

```python
import edgy


class User(edgy.Model):
    is_active: bool = edgy.BooleanField(default=True)


class Profile(edgy.Model):
    is_enabled: bool = edgy.BooleanField(default=True)


class MyModel(edgy.Model):
    user: User = edgy.ForeignKey("User", on_delete=edgy.CASCADE)
    profile: Profile = edgy.ForeignKey(Profile, on_delete=edgy.CASCADE, related_name="my_models")
    ...

```

##### Parameters

* **to** - A string [model](./models.md) name or a class object of that same model.
* **related_name** - The name to use for the relation from the related object back to this one.
* **on_delete** - A string indicating the behaviour that should happen on delete of a specific
model. The available values are `CASCADE`, `SET_NULL`, `RESTRICT` and those can also be imported
from `edgy`.
* **on_update** - A string indicating the behaviour that should happen on update of a specific
model. The available values are `CASCADE`, `SET_NULL`, `RESTRICT` and those can also be imported
from `edgy`.

    ```python
    from edgy import CASCADE, SET_NULL, RESTRICT
    ```

#### RefForeignKey

```python
from edgy import RefForeignKey
```

This is unique to **Edgy** and has [dedicated place](./reference-foreignkey.md) in the documentation
just to explain what it is and how to use it.

#### ManyToMany

```python
from typing import List
import edgy


class User(edgy.Model):
    is_active: bool = edgy.BooleanField(default=True)


class Organisation(edgy.Model):
    is_enabled: bool = edgy.BooleanField(default=True)


class MyModel(edgy.Model):
    users: List[User] = edgy.ManyToMany(User)
    organisations: List[Organisation] = edgy.ManyToMany("Organisation")

```

!!! Tip
    You can use `edgy.ManyToManyField` as alternative to `ManyToMany` instead.

##### Parameters

* **to** - A string [model](./models.md) name or a class object of that same model.
* **related_name** - The name to use for the relation from the related object back to this one.
* **through** - The model to be used for the relationship. Edgy generates the model by default
if none is provided.

#### IPAddressField

```python
import edgy


class MyModel(edgy.Model):
    ip_address: str = edgy.IPAddressField()
    ...

```

Derives from the same as [CharField](#charfield) and validates the value of an IP. It currently
supports `ipv4` and `ipv6`.

#### JSONField

```python
from typing import Dict, Any
import edgy


class MyModel(edgy.Model):
    data: Dict[str, Any] = edgy.JSONField(default={})
    ...

```

Simple JSON representation object.

#### OneToOne

```python
import edgy


class User(edgy.Model):
    is_active: bool = edgy.BooleanField(default=True)


class MyModel(edgy.Model):
    user: User = edgy.OneToOne("User")
    ...

```

Derives from the same as [ForeignKey](#foreignkey) and applies a One to One direction.

!!! Tip
    You can use `edgy.OneToOneField` as alternative to `OneToOne` instead.

#### TextField

```python
import edgy


class MyModel(edgy.Model):
    data: str = edgy.TextField(null=True, blank=True)
    ...

```

Similar to [CharField](#charfield) but has no `max_length` restrictions.

#### PasswordField

```python
import edgy


class MyModel(edgy.Model):
    data: str = edgy.PasswordField(null=False, max_length=255)
    ...

```

Similar to [CharField](#charfield) and it can be used to represent a password text.

#### TimeField

```python
import datetime
import edgy


def get_time():
    return datetime.datetime.now().time()


class MyModel(edgy.Model):
    time: datetime.time = edgy.TimeField(default=get_time)
    ...

```

#### URLField

```python
import edgy


class MyModel(edgy.Model):
    url: str = fields.URLField(null=True, max_length=1024)
    ...

```

Derives from the same as [CharField](#charfield) and validates the value of an URL.

#### UUIDField

```python
from uuid import UUID
import edgy


class MyModel(edgy.Model):
    uuid: UUID = fields.UUIDField()
    ...

```

Derives from the same as [CharField](#charfield) and validates the value of an UUID.



## Custom Fields

### Simple fields

If you merely want to customize an existing field in `edgy.db.fields.core` you can just inherit from it and provide the customization via the `FieldFactory` (or you can `FieldFactory` for handling a new sqlalchemy type).
Valid methods to overwrite are `__new__`, `get_column_type`, `get_pydatic_type`, `get_constraints` and `validate`

For examples look in the mentioned path (replace dots with slashes).


### Extended, special fields

If you want to customize the entire field (e.g. checks), you have to split the field in 2 parts:

- One inherits from `edgy.db.fields.base.BaseField` (or one of the derived classes) and provides the missing parts. It shall not be used for the Enduser (though possible).
- One inherits from `edgy.db.fields.field.FieldFactory`. Here the _bases attribute is adjusted to point to the Field from the first step.

Fields have to inherit from `edgy.db.fields.base.BaseField` and to provide following methods to work:

* **get_columns(self, field_name)** - returns the sqlalchemy columns which should be created by this field.
* **clean(self, field_name, value)** - returns the cleaned column values.

Additional they can provide following methods:
* **`__get__(self, instance, owner=None)`** - Descriptor protocol like get access customization. Second parameter contains the class where the field was specified.
* **`__set__(self, instance, value)`** - Descriptor protocol like set access customization. Dangerous to use. Better use to_model.
* **to_model(self, field_name, phase="")** - like clean, just for setting attributes or initializing a model. It is also used when setting attributes or in initialization (phase contains the phase where it is called). This way it is much more powerful than `__set__`
* **get_embedded_fields(self, field_name, fields_mapping)** - Define internal fields.
* **get_default_values(self, field_name, cleaned_data)** - returns the default values for the field. Can provide default values for embedded fields. If your field spans only one column you can also use the simplified get_default_value instead. This way you don't have to check for collisions. By default get_default_value is used internally.
* **get_default_value(self)** - return default value for one column fields.
* **get_global_constraints(self, field_name, columns)** - takes as second parameter (self excluded) the columns defined by this field (by get_columns). Returns a global constraint, which can be multi-column.

You should also provide an init method which sets following attributes:

* **column_type** - either None (default) or the sqlalchemy column type


Note: instance checks can also be done against the `field_type` attribute in case you want to check the compatibility with other fields (composite style)

The `annotation` parameter is for pydantic, the `__type___` parameter is transformed into the `field_type` attribute


for examples have a look in `tests/fields/test_composite_fields.py` or in `edgy/core/db/fields/core.py`
