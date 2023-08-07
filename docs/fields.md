# Fields

Fields are what is used within model declaration (data types) and defines wich types are going to
be generated in the SQL database when generated.

## Data types

As **Saffier** is a new approach on the top of Encode ORM, the following keyword arguments are
supported in **all field types**.

!!! Check
    The data types are also very familiar for those with experience with Django model fields.

* **primary_key** - A boolean. Determine if a column is primary key.
Check the [primary_key](./models.md#restrictions-with-primary-keys) restrictions with Saffier.
* **null** - A boolean. Determine if a column allows null.
* **default** - A value or a callable (function).
* **index** - A boolean. Determine if a database index should be created.
* **unique** - A boolean. Determine if a unique constraint should be created for the field.
Check the [unique_together](./models.md#unique-together) for more details.

All the fields are required unless on the the following is set:

* **null** - A boolean. Determine if a column allows null.

    <sup>Set default to `None`</sup>

* **blank** - A boolean. Determine if empry strings are allowed. This can be useful if you want to
build an admin-like application.

    <sup>Set default to `""`</sup>

* **default** - A value or a callable (function).
* **server_default** - nstance, str, Unicode or a SQLAlchemy `sqlalchemy.sql.expression.text`
construct representing the DDL DEFAULT value for the column.
* **comment** - A comment to be added with the field in the SQL database.

## Available fields

Saffier is built on the top of **pydantic** and inspired by `typesystem`. This means, for example,
that migrating from the Encode ORM is almost direct as it was made sure the same patterns, names,
and internal validation remained the same, intentionally.

To make the interface even more familiar, the field names end with a `Field` at the end.

### Importing fields

You have a few ways of doing this and those are the following:

```python
import saffier
```

From `saffier` you can access all the available fields.

```python
from saffier.db.models import fields
```

From `fields` you should be able to access the fields directly.

```python
from saffier.db.models.fields import BigIntegerField
```

You can import directly the desired field.

All the fields have specific parameters beisdes the ones [mentioned in data types](#data-types).

#### BigIntegerField

```python
import saffier


class MyModel(saffier.Model):
    big_number = saffier.BigIntegerField(default=0)
    another_big_number = saffier.BigIntegerField(minimum=10)
    ...

```

This field is used as a default field for the `id` of a model.

##### Parameters:

* **minimum** - An integer, float or decimal indicating the minimum.
* **maximum** - An integer, float or decimal indicating the maximum.
* **exclusive_minimum** - An integer, float or decimal indicating the exclusive minimum.
* **exclusive_maximum** - An integer, float or decimal indicating the exclusive maximum.
* **precision** - A string indicating the precision.
* **multiple_of** - An integer, float or decimal indicating the multiple of.

#### IntegerField

```python
import saffier


class MyModel(saffier.Model):
    a_number = saffier.IntegerField(default=0)
    another_number = saffier.IntegerField(minimum=10)
    ...

```

##### Parameters:

* **minimum** - An integer, float or decimal indicating the minimum.
* **maximum** - An integer, float or decimal indicating the maximum.
* **exclusive_minimum** - An integer, float or decimal indicating the exclusive minimum.
* **exclusive_maximum** - An integer, float or decimal indicating the exclusive maximum.
* **precision** - A string indicating the precision.
* **multiple_of** - An integer, float or decimal indicating the multiple of.

#### BooleanField

```python
import saffier


class MyModel(saffier.Model):
    is_active = saffier.BooleanField(default=True)
    is_completed = saffier.BooleanField(default=False)
    ...

```

#### CharField

```python
import saffier


class MyModel(saffier.Model):
    description = saffier.CharField(max_length=255)
    title = saffier.CharField(max_length=50, minimum_length=200)
    ...

```

##### Parameters:

* **max_length** - An integer indicating the total length of string.
* **min_length** - An integer indicating the minimum length of string.

#### ChoiceField

```python
from enum import Enum
import saffier

class Status(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class MyModel(saffier.Model):
    status = saffier.ChoiceField(choices=Status, default=Status.ACTIVE)
    ...

```

##### Parameters

* **choices** - An enum containing the choices for the field.

#### DateField

```python
import datetime
import saffier


class MyModel(saffier.Model):
    created_at = saffier.DateField(default=datetime.date.today)
    ...

```

##### Parameters

* **auto_now** - A boolean indicating the `auto_now` enabled.
* **auto_now_add** - A boolean indicating the `auto_now_add` enabled.


#### DateTimeField

```python
import datetime
import saffier


class MyModel(saffier.Model):
    created_at = saffier.DateTimeField(datetime.datetime.now)
    ...

```

##### Parameters

* **auto_now** - A boolean indicating the `auto_now` enabled.
* **auto_now_add** - A boolean indicating the `auto_now_add` enabled.


#### DecimalField

```python
import saffier


class MyModel(saffier.Model):
    price = saffier.DecimalField(max_digits=5, decimal_places=2, null=True)
    ...

```

##### Parameters

* **max_digits** - An integer indicating the total maximum digits.
* **decimal_places** - An integer indicating the total decimal places.

#### EmailField

```python
import saffier


class MyModel(saffier.Model):
    email = saffier.EmailField(max_length=60, null=True)
    ...

```

Derives from the same as [CharField](#charfield) and validates the email value.

#### FloatField

```python
import saffier


class MyModel(saffier.Model):
    email = saffier.FloatField(null=True)
    ...

```

Derives from the same as [IntergerField](#integerfield) and validates the decimal float.

#### ForeignKey

```python
import saffier


class User(saffier.Model):
    is_active = saffier.BooleanField(default=True)


class Profile(saffier.Model):
    is_enabled = saffier.BooleanField(default=True)


class MyModel(saffier.Model):
    user = saffier.ForeignKey("User", on_delete=saffier.CASCADE)
    profile = saffier.ForeignKey(Profile, on_delete=saffier.CASCADE, related_name="my_models")
    ...

```

##### Parameters

* **to** - A string [model](./models.md) name or a class object of that same model.
* **related_name** - The name to use for the relation from the related object back to this one.
* **on_delete** - A string indicating the behaviour that should happen on delete of a specific
model. The available values are `CASCADE`, `SET_NULL`, `RESTRICT` and those can also be imported
from `saffier`.
* **on_update** - A string indicating the behaviour that should happen on update of a specific
model. The available values are `CASCADE`, `SET_NULL`, `RESTRICT` and those can also be imported
from `saffier`.

    ```python
    from saffier import CASCADE, SET_NULL, RESTRICT
    ```

#### ManyToManyField

```python
import saffier


class User(saffier.Model):
    is_active = saffier.BooleanField(default=True)


class Organisation(saffier.Model):
    is_enabled = saffier.BooleanField(default=True)


class MyModel(saffier.Model):
    users = saffier.ManyToManyField(User)
    organisations = saffier.ManyToManyField(Organisation)

```

!!! Tip
    You can use `saffier.ManyToMany` as alternative to `ManyToManyField` instead.

##### Parameters

* **to** - A string [model](./models.md) name or a class object of that same model.
* **related_name** - The name to use for the relation from the related object back to this one.
* **through** - The model to be used for the relationship. Saffier generates the model by default
if none is provided.

#### IPAddressField

```python
import saffier


class MyModel(saffier.Model):
    ip_address = saffier.IPAddressField()
    ...

```

Derives from the same as [CharField](#charfield) and validates the value of an IP. It currently
supports `ipv4` and `ipv6`.

#### JSONField

```python
import saffier


class MyModel(saffier.Model):
    data = saffier.JSONField(default={})
    ...

```

Simple JSON representation object.

#### OneToOneField

```python
import saffier


class User(saffier.Model):
    is_active = saffier.BooleanField(default=True)


class MyModel(saffier.Model):
    user = saffier.OneToOneField("User")
    ...

```

Derives from the same as [ForeignKey](#foreignkey) and applies a One to One direction.

!!! Tip
    You can use `saffier.OneToOne` as alternative to `OneToOneField` instead.

#### TextField

```python
import saffier


class MyModel(saffier.Model):
    data = saffier.TextField(null=True, blank=True)
    ...

```

Similar to [CharField](#charfield) but has no `max_length` restrictions.

#### PasswordField

```python
import saffier


class MyModel(saffier.Model):
    data = saffier.PasswordField(null=False, max_length=255)
    ...

```

Similar to [CharField](#charfield) and it can be used to represent a password text.

#### TimeField

```python
import datetime
import saffier


def get_time():
    return datetime.datetime.now().time()


class MyModel(saffier.Model):
    time = saffier.TimeField(default=get_time)
    ...

```

##### Parameters

* **auto_now** - A boolean indicating the `auto_now` enabled.
* **auto_now_add** - A boolean indicating the `auto_now_add` enabled.

#### URLField

```python
import saffier


class MyModel(saffier.Model):
    url = fields.URLField(null=True, max_length=1024)
    ...

```

Derives from the same as [CharField](#charfield) and validates the value of an URL.

#### UUIDField

```python
import saffier


class MyModel(saffier.Model):
    uuid = fields.UUIDField()
    ...

```

Derives from the same as [CharField](#charfield) and validates the value of an UUID.
