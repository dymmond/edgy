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
* **default** - A value or a callable (function).
* **index** - A boolean. Determine if a database index should be created.
* **unique** - A boolean. Determine if a unique constraint should be created for the field.
Check the [unique_together](./models.md#unique-together) for more details.

All the fields are required unless on the the following is set:

* **null** - A boolean. Determine if a column allows null.

    <sup>Set default to `None`</sup>

* **server_default** - nstance, str, Unicode or a SQLAlchemy `sqlalchemy.sql.expression.text`
construct representing the DDL DEFAULT value for the column.
* **comment** - A comment to be added with the field in the SQL database.

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

#### DateField

```python
import datetime
import edgy


class MyModel(edgy.Model):
    created_at: datetime.date = edgy.DateField(default=datetime.date.today)
    ...

```

##### Parameters

* **auto_now** - A boolean indicating the `auto_now` enabled.
* **auto_now_add** - A boolean indicating the `auto_now_add` enabled.


#### DateTimeField

```python
import datetime
import edgy


class MyModel(edgy.Model):
    created_at: datetime.datetime = edgy.DateTimeField(datetime.datetime.now)
    ...

```

##### Parameters

* **auto_now** - A boolean indicating the `auto_now` enabled.
* **auto_now_add** - A boolean indicating the `auto_now_add` enabled.


#### DecimalField

```python
import decimal
import edgy

class MyModel(edgy.Model):
    price: decimal.Decimal = edgy.DecimalField(max_digits=5, decimal_places=2, null=True)
    ...

```

##### Parameters

* **max_digits** - An integer indicating the total maximum digits.
* **decimal_places** - An integer indicating the total decimal places.

#### EmailField

```python
import edgy


class MyModel(edgy.Model):
    email: str = edgy.EmailField(max_length=60, null=True)
    ...

```

Derives from the same as [CharField](#charfield) and validates the email value.

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

#### ManyToManyField

```python
from typing import List
import edgy


class User(edgy.Model):
    is_active: bool = edgy.BooleanField(default=True)


class Organisation(edgy.Model):
    is_enabled: bool = edgy.BooleanField(default=True)


class MyModel(edgy.Model):
    users: List[User] = edgy.ManyToManyField(User)
    organisations: List[Organisation] = edgy.ManyToManyField(Organisation)

```

!!! Tip
    You can use `edgy.ManyToMany` as alternative to `ManyToManyField` instead.

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

#### OneToOneField

```python
import edgy


class User(edgy.Model):
    is_active: bool = edgy.BooleanField(default=True)


class MyModel(edgy.Model):
    user: User = edgy.OneToOneField("User")
    ...

```

Derives from the same as [ForeignKey](#foreignkey) and applies a One to One direction.

!!! Tip
    You can use `edgy.OneToOne` as alternative to `OneToOneField` instead.

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

##### Parameters

* **auto_now** - A boolean indicating the `auto_now` enabled.
* **auto_now_add** - A boolean indicating the `auto_now_add` enabled.

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
