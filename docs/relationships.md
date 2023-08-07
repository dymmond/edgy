# Relationships

Creating relationships in **Saffier** is as simple as importing the fields and apply them into
the models.

There are currently two types, the [ForeignKey](./fields.md#foreignkey)
and the [OneToOneField](./fields.md#onetoonefield).

When declaring a foreign key, you can pass the value in two ways, as a string or as a model
object. Internally **Saffier** lookups up inside the [registry](./models.md#registry) and maps
your fields.

When declaring a model you can have one or more ForeignKey pointing to different tables or
multiple foreign keys pointing to the same table as well.

!!! Tip
    Have a look at the [related name](./queries/related-name.md) documentation to understand how
    you can leverage reverse queries with foreign keys.

## ForeignKey

Let us define the following models `User` and `Profile`.

```python
{!> ../docs_src/relationships/model.py !}
```

Now let us create some entries for those models.

```python
user = await User.query.create(first_name="Foo", email="foo@bar.com")
await Profile.query.create(user=user)

user = await User.query.create(first_name="Bar", email="bar@foo.com")
await Profile.query.create(user=user)
```

### Multiple foreign keys pointing to the same table

What if you want to have multiple foreign keys pointing to the same model? This is also easily
possible to achieve.

```python hl_lines="20-29"
{!> ../docs_src/relationships/multiple.py !}
```

!!! Tip
    Have a look at the [related name](./queries/related-name.md) documentation to understand how
    you can leverage reverse queries with foreign keys withe the
    [related_name](./queries/related-name.md#related_name-attribute).

### Load an instance without the foreign key relationship on it

```python
profile = await Profile.query.get(id=1)

# We have an album instance, but it only has the primary key populated
print(profile.user)       # User(id=1) [sparse]
print(profile.user.pk)    # 1
print(profile.user.email)  # Raises AttributeError
```

### Load an instance with the foreign key relationship on it

```python
profile = await Profile.query.get(user__id=1)

await profile.user.load() # loads the foreign key
```

### Load an instance with the foreign key relationship on it with select related

```python
profile = await Profile.query.select_related("user").get(id=1)

print(profile.user)       # User(id=1) [sparse]
print(profile.user.pk)    # 1
print(profile.user.email)  # foo@bar.com
```

## ForeignKey constraints

As mentioned in the [foreign key field](./fields.md#foreignkey), you can specify constraints in
a foreign key.

The available values are `CASCADE`, `SET_NULL`, `RESTRICT` and those can also be imported
from `saffier`.

```python
from saffier import CASCADE, SET_NULL, RESTRICT
```

When declaring a foreign key or a one to one key, the **on_delete must be provided** or an
`AssertationError` is raised.

Looking back to the previous example.

```python hl_lines="20"
{!> ../docs_src/relationships/model.py !}
```

`Profile` model defines a `saffier.ForeignKey` to the `User` with `on_delete=saffier.CASCADE` which
means that whenever a `User` is deleted from the database, all associated `Profile` instances will
also be removed.

### Delete options

* **CASCADE** - Remove all referencing objects.
* **RESTRICT** - Restricts the removing referenced objects.
* **SET_NULL** - This will make sure that when an object is deleted, the associated referencing
instances pointing to that object will set to null. When this `SET_NULL` is true, the `null=True`
must be also provided or an `AssertationError` is raised.

## OneToOneField

Creating an `OneToOneField` relationship between models is basically the same as the
[ForeignKey](#foreignkey) with the key difference that it uses `unique=True` on the foreign key
column.

```python hl_lines="20"
{!> ../docs_src/relationships/onetoone.py !}
```

The same rules for this field are the same as the [ForeignKey](#foreignkey) as this derives from it.

Let us create a `User` and a `Profile`.

```python
user = await User.query.create(email="foo@bar.com")
await Profile.query.create(user=user)
```

Now creating another `Profile` with the same user will fail and raise an exception.

```
await Profile.query.create(user=user)
```
