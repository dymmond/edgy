# Fields

Fields are what is used within model declaration (data types) and defines wich types are going to
be generated in the SQL database when generated.

## Data types

As **Edgy** is a new approach on the top of Encode ORM, the following keyword arguments are
supported in **all field types**.

!!! Check
    The data types are also very familiar for those with experience with Django model fields.

- `primary_key` - A boolean. Determine if a column is primary key.
Check the [primary_key](./models.md#restrictions-with-primary-keys) restrictions with Edgy.
- `exclude` - An bool indicating if the field is included in model_dump
- `index` - A boolean. Determine if a database index should be created.
- `inherit` - A boolean. Determine if a field can be inherited in submodels. Default is True. It is used by PKField, RelatedField and the injected ID Field.
- `skip_absorption_check` - A boolean. Default False. Dangerous option! By default when defining a CompositeField with embedded fields and the `absorb_existing_fields` option it is checked that the field type of the absorbed field is compatible with the field type of the embedded field. This option skips the check.
- `skip_reflection_type_check` -  A boolean. Default False. Skip reflection column type check.
- `unique` - A boolean. Determine if a unique constraint should be created for the field.
Check the [unique_together](./models.md#unique-together) for more details.
- `column_name` - A string. Database name of the column (by default the same as the name).
- `comment` - A comment to be added with the field in the SQL database.
- `secret` - A special attribute that allows to call the [exclude_secrets](./queries/secrets.md#exclude-secrets) and avoid
accidental leakage of sensitive data.

All fields are required unless one of the following is set:

- `null` - A boolean. Determine if a column allows null.

    <sup>Set default to `None`</sup>

- `server_default` - instance, str, Unicode or a SQLAlchemy `sqlalchemy.sql.expression.text`
construct representing the DDL DEFAULT value for the column.
- `default` - A value or a callable (function).
- `auto_now` or `auto_now_add` -  Only for DateTimeField and DateField


!!! Tip
    Despite not always advertised you can pass valid keyword arguments for pydantic FieldInfo (they are in most cases just passed through).

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

!!! Note
    For sqlite with autoincrement an integer field is used. Sqlite doesn't support BigInteger for autoincrement.

##### Parameters:

* `minimum` - An integer indicating the minimum.
* `maximum` - An integer indicating the maximum.
* `multiple_of` - An integer indicating the multiple of.
* `increment_on_save` - An integer which is applied on every save.

#### IntegerField

```python
import edgy


class MyModel(edgy.Model):
    a_number: int = edgy.IntegerField(default=0)
    another_number: int = edgy.IntegerField(minimum=10)
    ...
```

##### Parameters:

* `minimum` - An integer indicating the minimum.
* `maximum` - An integer indicating the maximum.
* `multiple_of` - An integer indicating the multiple of.
* `increment_on_save` - An integer which is applied on every save.


#### SmallIntegerField

```python
import edgy


class MyModel(edgy.Model):
    a_number: int = edgy.SmallIntegerField(default=0)
    another_number: int = edgy.SmallIntegerField(minimum=10)
    ...
```

##### Parameters:

* `minimum` - An integer indicating the minimum.
* `maximum` - An integer indicating the maximum.
* `multiple_of` - An integer indicating the multiple of.
* `increment_on_save` - An integer which is applied on every save.

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

* `max_length` - An integer indicating the total length of string. Required. Set to None for creating a field without a string length restriction.
* `min_length` - An integer indicating the minimum length of string.

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

* `choices` - An enum containing the choices for the field.

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
the fields need the exclude attribute/parameter set.

!!! Note
    The inherit flag is set to False for all fields created by a composite. This is because of inheritance.

##### Parameters

* `inner_fields` - Required. A sequence containing the external field names mixed with embedded field definitions (name, Field) tuples.
                     As an alternative it is possible to provide an Edgy Model (abstract or non-abstract) or a dictionary in the format: key=name, value=Field
* `unsafe_json_serialization` - Default False. Normally when serializing in json mode, CompositeFields are ignored when they don't have a pydantic model set. This option includes such CompositeFields in the dump.
* `absorb_existing_fields` - Default False. Don't fail if fields speficied with (name, Field) tuples already exists. Treat them as internal fields. The existing fields are checked if they are a subclass of the Field or have the attribute `skip_absorption_check` set
* `model` - Default None (not set).Return a pydantic model instead of a dict.
* `prefix_embedded` - Default "". Prefix the field names of embedded fields (not references to external fields). Useful for implementing embeddables

Note: embedded fields are shallow-copied. This way it is safe to provide the same inner_fields object to multiple CompositeFields.


Note: there is a special parameter for model: `ConditionalRedirect`.
It changes the behaviour of CompositeField in this way:

- `inner_fields` with 1 element: Reads and writes are redirected to this field. When setting a dict or pydantic BaseModel the value is tried to be extracted like in the normal mode. Otherwise the logic of the single field is used. When returning only the value of the single field is returned
- `inner_fields` with >1 element: normal behavior. Dicts are returned

##### Inheritance

CompositeFields are evaluated in non-abstract models. When overwritten by another field and the evaluation didn't take place yet no fields are generated.

When overwritten after evaluation the fields are still lingering around.

You can also overwrite from CompositeField generated fields in subclasses regardless if the CompositeField used absorb_existing_fields inside.

You may want to use **ExcludeField** to remove fields.


#### ComputedField

This is a pseudo field similar to the GeneratedField of Django. It is different in the way it operates on
an instance instead of a sql query and supports setting values. It features also a string getter/setter (which retrieves the getter/setter from the class) and
a fallback_getter which is used in case the getter is not available.
It is used in the contrib permissions feature.

```python
import edgy

class BasePermission(edgy.Model):
    name: str = edgy.fields.CharField(max_length=100, null=False)
    description: Optional[str] = edgy.fields.ComputedField(
        getter="get_description",  # uses the getter classmethod/staticmethod of the class/subclass
        setter="set_description",  # uses the setter classmethod/staticmethod of the class/subclass
        fallback_getter=lambda field, instance, owner: instance.name,  # fallback to return the name
    )
    @classmethod
    def get_description(cls, field, instance, owner=None) -> str:
        return instance.name

    @classmethod
    def set_description(cls, field, instance, value) -> None:
        instance.name = value
```

##### Parameters

- getter (Optional) -String to classmethod/staticmethod or a callable. Getter which is used to provide a value in model_dump or on direct access to the field.
- setter (Optional) -String to classmethod/staticmethod or a callable. Setter which is executed when assigning a value to the field. If not provided assignments are simply dismissed.
- fallback_getter (Optional) -Callable. Is used as fallback when the getter was not found. Useful for inheritance so subclasses can provide a getter but works also without.


#### DateField

```python
import datetime
import edgy


class MyModel(edgy.Model):
    created_at: datetime.date = edgy.DateField(default=datetime.date.today)
    ...

```

!!! Note
    Internally the DateTimeField logic is used and only the date element returned.
    This implies the field can handle the same types like DateTimeField.

##### Parameters

* `auto_now` - A boolean indicating the `auto_now` enabled. Useful for auto updates.
* `auto_now_add` - A boolean indicating the `auto_now_add` enabled. This will ensure that it is
only added once.
* `default_timezone` - ZoneInfo containing the timezone which is added to naive datetimes and used for `auto_now` and `auto_now_add`.
                         Datetimes are converted to date and lose their timezone information.
* `force_timezone` - ZoneInfo containing the timezone in which all datetimes are converted.
                       For naive datetimes it behaves like `default_timezone`
                       Datetimes are converted to date and lose their timezone information.


!!! Note
    There is no `remove_timezone` (argument will be silently ignored).


!!! Note
    `auto_now` and `auto_now_add` set the `read_only` flag by default. You can explicitly set `read_only` to `False` to be still able to update the field manually.

#### DateTimeField

```python
import datetime
import edgy


class MyModel(edgy.Model):
    created_at: datetime.datetime = edgy.DateTimeField(default=datetime.datetime.now)
    ...

```

DateTimeField supports int, float, string (isoformat), date object and of course datetime as input. They are automatically converted to datetime.


##### Parameters

* `auto_now` - A boolean indicating the `auto_now` enabled. Useful for auto updates.
* `auto_now_add` - A boolean indicating the `auto_now_add` enabled. Only set when creating the object
* `default_timezone` - ZoneInfo containing the timezone which is added to naive datetimes
* `force_timezone` - ZoneInfo containing the timezone in which all datetimes are converted.
                         For naive datetimes it behaves like `default_timezone`
* `remove_timezone` - Boolean. Default False. Remove timezone information from datetime. Useful if the db should only contain naive datetimes and not convert.
* `with_timezone` - Boolean. Defaults to True for remove_timezone is False. It controls if timezones are included on db side. You most probably don't need setting it except you want a naive datetime saving in a timezone aware column which makes no sense.


!!! Note
    `auto_now` and `auto_now_add` set the `read_only` flag by default. You can explicitly set `read_only` to `False` to be still able to update the field manually.

#### DurationField

A DurationField can save the amount of time of a process. This is useful in case there is no clear start/stop timepoints.
For example the time worked on a project.


```python
import datetime
import edgy

class Project(edgy.Model):
    worked: datetime.timedelta = edgy.DurationField(default=datetime.timedelta())
    estimated_time: datetime.timedelta = edgy.DurationField()
    ...
```

#### DecimalField

```python
import decimal
import edgy

class MyModel(edgy.Model):
    price: decimal.Decimal = edgy.DecimalField(max_digits=5, decimal_places=2, null=True)
    ...
```

##### Parameters

* `minimum` - An integer indicating the minimum.
* `maximum` - An integer indicating the maximum.
* `max_digits` - An integer indicating the total maximum digits. Optional.
* `decimal_places` - An integer indicating the total decimal places.
* `multiple_of` - An integer, float or decimal indicating the multiple of.

#### EmailField

```python
import edgy


class MyModel(edgy.Model):
    email: str = edgy.EmailField(max_length=60, null=True)
    ...
```

Derives from the same as [CharField](#charfield) and validates the email value.

##### Parameters

- `max_length` - Integer/None. Default: 255.

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

#### FileField

See [FileField](file-handling.md#filefield).

#### ImageField

See [ImageField](file-handling.md#imagefield).

#### FloatField

```python
import edgy


class MyModel(edgy.Model):
    price: float = edgy.FloatField(null=True)
    ...
```

Derives from the same as [IntegerField](#integerfield) and validates the float.

##### Parameters

* `max_digits` - An integer indicating the total maximum digits.
    In contrast to DecimalField it is database-only and can be used for higher/lower precision fields.
    It is also available under the name `precision` with a higher priority. Optional.

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

Hint you can change the base for the reverse end with embed_parent:


```python hl_lines="26"
{!> ../docs_src/relationships/embed_parent_with_embedded.py !}
```

when on the user model the `profile` reverse link is queried, by default the address embeddable is returned.
Queries continue to use the Profile Model as base because address isn't a RelationshipField.
The Profile object can be accessed by the `profile` attribute we choosed as second parameter.

When the second parameter is empty, the parent object is not included as attribute.

The reverse end of a `ForeignKey` is a [Many to one relation](./queries/many-to-one.md).


##### Parameters

* `to` - A string [model](./models.md) name or a class object of that same model.
* `target_registry` - Registry where the model callback is installed if `to` is a string. Defaults to the field owner registry.
* `related_name` - The name to use for the relation from the related object back to this one. Can be set to `False` to disable a reverse connection.
                     Note: Setting to `False` will also prevent prefetching and reversing via `__`.
                     See also [related_name](./queries/related-name.md) for defaults
* `related_fields` - The columns or fields to use for the foreign key. If unset or empty, the primary key(s) are used.
* `embed_parent` (to_attr, as_attr) - When accessing the reverse relation part, return to_attr instead and embed the parent object in as_attr (when as_attr is not empty). Default None (which disables it). For to_attr (first argument) deeply nested models can be selected via `__`.
* `no_constraint` - Skip creating a constraint. Note: if set and index=True an index will be created instead.
* `remove_referenced` - (Default `False`) - When deleting the model, the referenced model is also deleted.
* `on_delete` - A string indicating the behaviour that should happen on delete of a specific
model. The available values are `CASCADE`, `SET_NULL`, `RESTRICT` and those can also be imported
from `edgy`.
* `on_update` - A string indicating the behaviour that should happen on update of a specific
model. The available values are `CASCADE`, `SET_NULL`, `RESTRICT` and those can also be imported
from `edgy`.
    ```python
    from edgy import CASCADE, SET_NULL, RESTRICT
    ```
* `relation_fn` - Optionally drop a function which returns a Relation for the reverse side. This will be used by the RelatedField (if it is created). Used by the ManyToMany field.
* `reverse_path_fn` - Optionally drop a function which handles the traversal from the reverse side. Used by the ManyToMany field.
- `column_name` - A string. Base database name of the column (by default the same as the name). Useful for models with special characters in their name.


!!! Note
    The index parameter can improve the performance and is strongly recommended especially with `no_constraint` but also
    ForeignKeys with constraint will benefit. By default off because conflicts are easily to provoke when reinitializing models (tests with database fixture scope="function").
    This is no concern for webservers where models are initialized once.
    `unique` uses internally an index and `index=False` will be ignored.


!!! Note
    There is a `reverse_name` argument which can be used when `related_name=False` to specify a field for reverse relations.
    It is useless except if related_name is `False` because it is otherwise overwritten.
    The `reverse_name` argument is used for finding the reverse field of the relationship.


!!! Note
    When `embed_parent` is set, queries start to use the second parameter of `embed_parent` **if it is a RelationshipField**.
    If it is empty, queries cannot access the parent anymore when the first parameter points to a `RelationshipField`.
    This is mode is analogue to ManyToMany fields.
    Otherwise, the first parameter points not to a `RelationshipField` (e.g. embeddable, CompositeField), queries use still the model, without the prefix stripped.


!!! Note
    `embed_parent` cannot traverse embeddables.

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

* `to` - A string [model](./models.md) name or a class object of that same model.
* `target_registry` - Registry where the model callback is installed if `to` is a string. Defaults to the field owner registry.
* `from_fields` - Provide the `related_fields` for the implicitly generated ForeignKey to the owner model.
* `to_fields` - Provide the `related_fields` for the implicitly generated ForeignKey to the child model.
* `related_name` - The name to use for the relation from the related object back to this one.
* `through` - The model to be used for the relationship. Edgy generates the model by default
                if None is provided or `through` is an abstract model.
* `through_registry` - Registry where the model callback is installed if `through` is a string or empty. Defaults to the field owner registry.
* `through_tablename` - Custom tablename for `through`. E.g. when special characters are used in model names.
* `embed_through` - When traversing, embed the through object in this attribute. Otherwise it is not accessable from the result.
                      if an empty string was provided, the old behaviour is used to query from the through model as base (default).
                      if False, the base is transformed to the target and source model (full proxying). You cannot select the through model via path traversal anymore (except from the through model itself).
                      If not an empty string, the same behaviour like with False applies except that you can select the through model fields via path traversal with the provided name.


!!! Note
    If `through` is an abstract model it will be used as a template (a new model is generated with through as base).


!!! Note
    The index parameter is passed through to the ForeignKey fields but is not required. The intern ForeignKey fields
    create with their primary key constraint and unique_together fallback their own index.
    You should be warned that the same for ForeignKey fields applies here for index, so you most probably don't want to use an index here.

!!! Note
    By default generated through models are not added to content types. You must either define a registered model or add an explicit `ContentTypeField` to the abstract.
    You can also modify the through model via the `through` attribute and add a `ContentTypeField` to the fields though not recommended (see [customizing fields](#customizing-fields-after-model-initialization)).

```python title="Example for through model with content_type"
{!> ../docs_src/contenttypes/m2m_with_contenttypes.py !}
```

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


#### BinaryField

Simple blob field. It supports on some dbs a `max_length` attribute.

```python
from typing import Dict, Any
import edgy


class MyModel(edgy.Model):
    data: bytes = edgy.Binary()
    ...

```

!!! Note
    Blobs (BinaryField) are like TextFields not size-restricted by default.

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
    You can use `edgy.OneToOneField` as alternative to `OneToOne` instead. Or if you want the basic ForeignKey with unique=True.

!!! Note
    The index parameter is here ignored.

#### TextField

```python
import edgy


class MyModel(edgy.Model):
    data: str = edgy.TextField(null=True)
    ...

```

Similar to [CharField](#charfield) but has no `max_length` restrictions.

#### PasswordField

```python
{!> ../docs_src/permissions/passwordfield_basic.py !}
```

Similar to [CharField](#charfield) and it can be used to represent a password text. The secret parameter defaults to `True`.

##### Parameters

- `max_length` - Integer/None. Default: 255.
- `derive_fn` - Callable. Default: None. When provided it automatically hashes an incoming string. Should be a good key deriving function.
- `keep_original` - Boolean. Default: `True` when `derive_fn` is provided `False` otherwise. When True, an attribute named: `<fieldname>_original` is added
  whenever a password is manually set. It contains the password in plaintext. After saving/loading the attribute is set to `None`.

Ideally the key derivation function includes the parameters (and derive algorithm) used for deriving in the hash so a compare_pw function can reproduce the result.

For more examples see [Passwords](./permissions/passwords.md).

#### PlaceholderField

A field without a column. In some way it behaves like a plain pydantic field with edgy features. It is useful to store user-facing variables, like
the original password of PasswordField, so it isn't ignored/causes an error when using a `StrictModel`.

Most users will may prefer the ComputedField instead.

##### Parameters

- pydantic_field_type: define the pydantic field type. Optionally.


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

- * `with_timezone` - Boolean. Default `False`. Enable timezone support for time in the db.

#### URLField

```python
import edgy


class MyModel(edgy.Model):
    url: str = fields.URLField(null=True, max_length=1024)
    ...
```

Derives from the same as [CharField](#charfield) and validates the value of an URL.

##### Parameters

- `max_length` - Integer/None. Default: 255.

#### UUIDField

```python
from uuid import UUID
import edgy

class MyModel(edgy.Model):
    uuid: UUID = fields.UUIDField()
    ...
```

Derives from the same as [CharField](#charfield) and validates the value of an UUID.

## Advanced Fieldpatterns

These are not actually fields but patterns.

### Revision Field

You remember the strange `increment_on_save` parameter on Integer like fields?

Here is how to use it.

#### Just counting up

The simplest case:


```python
import edgy


class MyModel(edgy.Model):
    rev: int = edgy.SmallIntegerField(default=0, increment_on_save=1)
    ...

async def main():
    obj = await MyModel.query.create()
    # obj.rev == 0
    await obj.save()
    # obj.rev == 1

```

What happens here? On every save the counter is in database increased. When accessing the attribute it is automatically loaded.

#### Revisioning

That is boring let's go farther. What happens when we make it a primary key?

Hint: it has a very special handling.



```python
import edgy

class MyModel(edgy.Model):
    id: int = edgy.IntegerField(primary_key=True, autoincrement=True)
    rev: int = edgy.SmallIntegerField(default=0, increment_on_save=1, primary_key=True)
    ...

async def main():
    obj = await MyModel.query.create()
    # obj.rev == 0
    await obj.save()
    # obj.rev == 1
    assert len(await MyModel.query.all()) == 2
```

This implements a copy on save. We have now revision safe models. This is very strictly checked.
It even works with FileFields or ImageFields.

#### Revisioning with unsafe updates

Sometimes you want to be able to modify old revisions. There is a second revisioning pattern allowing this:

```python
import edgy

class MyModel(edgy.Model):
    id: int = edgy.IntegerField(primary_key=True, autoincrement=True)
    document = edgy.fields.FileField(null=True)
    rev: int = edgy.SmallIntegerField(default=0, increment_on_save=1, primary_key=True, read_only=False)
    name = edgy.CharField(max_length=50)
    ...

async def main():
    obj = await MyModel.query.create(name="foo")
    # obj.rev == 0
    await obj.save()
    # obj.rev == 1
    assert len(await MyModel.query.all()) == 2
    # rev must be in update otherwise it fails (what is good)
    await obj.update(name="bar", rev=obj.rev)
```

### Countdown Field

Until now we have seen only `increment_on_save=1` but it can be also negative.
That is useful for a countdown.


```python
import edgy


class MyModel(edgy.Model):
    counter: int = edgy.IntegerField(increment_on_save=-1)
    ...

async def main():
    # we have no default here
    obj = await MyModel.query.create(counter=10)
    # obj.counter == 10
    await obj.save()
    # obj.counter == 9
    # we can reset
    await obj.save(values={"counter": 100})
    # obj.counter == 100
    # or specify a different default value
    obj = await MyModel.query.create(counter=50)
    # obj.counter == 50
```

## Custom Fields

### Factory fields

If you merely want to customize an existing field in `edgy.core.db.fields` you can just inherit from it and provide the customization via the `FieldFactory` (or you can use `FieldFactory` directly for handling a new sqlalchemy type).
Valid methods to overwrite are `__new__`, `get_column_type`, `get_pydantic_type`, `get_constraints`, `build_field` and `validate` as well as you can overwrite many field methods
by defining them on the factory (see `edgy.core.db.fields.factories` for allowed methods). Field methods overwrites must be classmethods which take as first argument after
the class itself the field object and a keyword arg original_fn which can be None in case none was defined.

For examples have a look in `edgy/core/db/fields/core.py`.


!!! Note
    You can extend in the factory the overwritable methods. The overwritten methods are not permanently overwritten. After init it is possible to change them again.
    A simple example is in `edgy/core/db/fields/exclude_field.py`. The magic behind this is in  `edgy/core/db/fields/factories.py`.

!!! Tip
    For global constraints you can overwrite the `get_global_constraints` field method via the factory overwrite. This differs from `get_constraints` which is defined on factories.

### Extended, special fields

If you want to customize the entire field (e.g. checks), you have to split the field in 2 parts:

- One inherits from `edgy.db.fields.base.BaseField` (or one of the derived classes) and provides the missing parts. It shall not be used for the Enduser (though possible).
- One inherits from `edgy.db.fields.factories.FieldFactory`. Here the field_bases attribute is adjusted to point to the Field from the first step.

Fields have to inherit from `edgy.db.fields.base.BaseField` and to provide following methods to work:

- `get_columns(self, field_name)` - returns the sqlalchemy columns which should be created by this field.
- `clean(self, field_name, value, to_query=False)` - returns the cleaned column values. to_query specifies if clean is used by the query sanitizer and must be more strict (no partial values).

Additional they can provide/overwrite following methods:

* `operator_to_clause` - Generates clauses for db from the result of clean. Implies clean is called with `for_query=True`.
* `__get__(self, instance, owner=None)` - Descriptor protocol like get access customization. Second parameter contains the class where the field was specified.
  To prevent unwanted loads operate on the instance `__dict__`. You can throw an AttributeError to trigger a load.
* `__set__(self, instance, value)` - Descriptor protocol like set access customization. Dangerous to use. Better use to_model.
* `to_model(self, field_name)` - like clean, just for setting attributes or initializing a model. It is also used when setting attributes or in initialization (phase contains the phase where it is called). This way it is much more powerful than `__set__`.
* `get_embedded_fields(self, field_name, fields)` - Define internal fields.
* `get_default_values(self, field_name, cleaned_data)` - returns the default values for the field. Can provide default values for embedded fields. If your field spans only one column you can also use the simplified get_default_value instead. This way you don't have to check for collisions. By default get_default_value is used internally.
* `get_default_value(self)` - return default value for one column fields.
* `get_global_constraints(self, field_name, columns, schemes)` - takes as second parameter (self excluded) the columns defined by this field (by get_columns). Returns a global constraint, which can be multi-column. The last one provides the schemes in descending priority.
* `modify_input(name, kwargs)`: Modifying the input (kwargs is a dict). E.g. providing defaults only when loaded from db or collecting fields and columns for a
  multi column, composite field (e.g. FileField). Note: this method is very powerful. You should only manipulate sub-fields and columns belonging to the field.
* `embed_field(prefix, new_fieldname, owner=None, parent=None)`: Controlling the embedding of the field in other fields. Return None to disable embedding.

You should also provide an init method which sets following attributes:

* `column_type` - either None (default) or the sqlalchemy column type
* `inject_default_on_partial_update` - Add default value despite being a partial update. Useful for implementing `auto_now` or other fields which should change on every update.


!!! Note
    Instance checks can also be done against the `field_type` attribute in case you want to check the compatibility with other fields (composite style).
    The `annotation` field parameter is for pydantic (automatically set by factories).
    For examples have a look in `tests/fields/test_composite_fields.py` or in `edgy/core/db/fields/core.py`.

!!! Note
    Instance parameters are always model instances.

### Tricks

#### Using for_query

`clean` is required to clean the values for the db. It has an extra parameter `for_query` which is set
in a querying context (searching something in the db).

When using a multi-column field, you can overwrite `operator_to_clause`. You may want to adjust clean called with
`for_query=True` so it returns are suitable holder object (e.g. dict) for the fieldname.
See `tests/fields/test_multi_column_fields.py` for an example.

#### Using phases

The `CURRENT_PHASE` ContextVariable contains the current phase. If used outside of a model context it defaults to an empty string.

Within a model context it contains the current phase it is called for:

* `init`: Called in model `__init__`.
* `init_db`: Called in model `__init__` when loaded from a row.
* `set`: Called in model `__setattr__` (when setting an attribute).
* `load`: Called after load. Contains db values.
* `post_insert`: Called after insert. Arguments are the ones passed to save.
* `post_update`: Called after update. Arguments are the ones passed to save.

For  `extract_column_values` following phases exist (except called manually):

* `prepare_insert`: Called in extract_column_values for insert.
* `prepare_update`: Called in extract_column_values for update.
* `compare`: Called when comparing model instances.

#### Using the instance

There are 2 ContextVar named `CURRENT_INSTANCE` and `CURRENT_MODEL_INSTANCE`. `CURRENT_INSTANCE` is the executing instance of a QuerySet or Model while
`CURRENT_MODEL_INSTANCE` is always a model instance or `None`. When calling manually also `CURRENT_INSTANCE` can be `None`.
They are available during setting an attribute, `transform_input` and `extract_column_values` calls when set as well as in the `pre_save_callback` or `post_save_callback` hooks.
This implies you can use them in all sub methods like get_default...

You may want to use the pre_save_callback with its instance parameter to ensure you get a model instance.

Note: When using in-db updates of QuerySet there is no instance.

Note: There is one exception of a QuerySet method which use a model instance as `CURRENT_INSTANCE`: `create`.


#### Finding out which values are explicit set

The `EXPLICIT_SPECIFIED_VALUES` ContextVar is either None or contains the key names of the explicit specified values.
It is set in `save` and `update`.

#### Saving variables on Field

You can use the field as a store for your customizations. Unconsumed keywords are set as attributes on the BaseField object.
But if the variables clash with the variables used for Columns or for pydantic internals, there are unintended side-effects possible.


#### Field returning persistent, instance aware object

For getting an immutable object attached to a Model instance, there are two ways:

- Using Managers (by default they are instance aware)
- Using fields with `__get__` and `to_model`.

The last way is a bit more complicated than managers. You need to consider 3 ways the field is affected:

1. `__init__` and `load`: Some values are passed to the field. Use `to_model` for providing an initial object with the CURRENT_INSTANCE context var.
    Note: this doesn't gurantee the initialization. We still need the  `__get__`-
2. `__getattr__` here the object can get an instance it can attach to. Use `__get__` for this.
3. Set access. Either use `__set__` or `to_model` so it uses the old value.

#### Nested loads with `__get__`

Fields using `__get__` must consider the context_var `MODEL_GETATTR_BEHAVIOR`. There are two modes to consider:

1. `passdown`: getattr access returns `AttributeError` on missing attributes. The first time an `AttributeError` is issued a load is issued when neccessary and the mode switches to `coro`. This can be overwritten in composite fields.
2. `coro`: `__get__` needs to issue the load itself (in case this is wanted) and to handle returned coroutines. AttributeErrors are passed through.

The third mode `load` is only relevant for models and querysets.


## Customizing fields after model initialization

Dangerous! There can be many side-effects, especcially for non-metafields (have columns or attributes).

If you just want to remove a field ExcludeField or the inherit flags are the ways to go.

Adding, replacing or deleting a field is triggering automatically a required invalidation and auto-registers in pydantic model_fields.
For non-metafields you may need to rebuild the model.

If you want to add/delete a Field dynamically, check `edgy/core/db/models/metaclasses.py` or `edgy/core/connection/registry.py`
first what is done. Sometimes you may need to update the annotations.
