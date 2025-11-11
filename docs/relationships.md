# Relationships

Establishing relationships between models in **Edgy** is straightforward, involving importing the necessary fields and applying them to your models.

Edgy currently supports two relationship types: [ForeignKey](./fields/index.md#foreignkey) and [OneToOne](./fields/index.md#onetoone).

When defining a foreign key, you can specify the related model either as a string or as a model object. Edgy internally resolves the relationship using the [registry](./models.md#registry).

A model can have one or more foreign keys pointing to different tables or multiple foreign keys referencing the same table.

!!! Tip
    Refer to the [related name](./queries/related-name.md) documentation to learn how to leverage reverse queries with foreign keys.

## ForeignKey

Let's define two models, `User` and `Profile`.

```python
{!> ../docs_src/relationships/model.py !}
```

Now, let's create some entries for these models.

```python
user = await User.query.create(first_name="Foo", email="foo@bar.com")
await Profile.query.create(user=user)

user = await User.query.create(first_name="Bar", email="bar@foo.com")
await Profile.query.create(user=user)
```

### Multiple Foreign Keys Pointing to the Same Table

You can have multiple foreign keys referencing the same model.

```python hl_lines="20-29"
{!> ../docs_src/relationships/multiple.py !}
```

!!! Tip
    Refer to the [related name](./queries/related-name.md) documentation to understand how to leverage reverse queries with foreign keys using the [related_name](./queries/related-name.md#related_name-attribute) attribute.

### Load an Instance Without the Foreign Key Relationship Populated

```python
profile = await Profile.query.get(id=1)

# We have a profile instance, but it only has the primary key populated
print(profile.user)       # User(id=1) [sparse]
print(profile.user.pk)    # 1
print(profile.user.email)  # Raises AttributeError
```

#### Load Recursively

Especially when using `model_dump`, it's helpful to populate all foreign keys. You can use `load_recursive` for this.

```python
profile = await Profile.query.get(id=1)
await profile.load_recursive()

# We have a profile instance and all foreign key relations populated
print(profile.user)       # User(id=1)
print(profile.user.pk)    # 1
print(profile.user.email)  # foo@bar.com
```

### Load an Instance with the Foreign Key Relationship Populated

```python
profile = await Profile.query.get(user__id=1)

await profile.user.load() # loads the foreign key
```

### Load an Instance with the Foreign Key Relationship Populated Using `select_related`

```python
profile = await Profile.query.select_related("user").get(id=1)

print(profile.user)       # User(id=1)
print(profile.user.pk)    # 1
print(profile.user.email)  # foo@bar.com
```

### Access Foreign Key Values Directly from the Model

!!! Note
    This is possible since Edgy version 0.9.0. Before this version, you had to use `select_related` or `load()`.

You can access foreign key values directly from the model instance without using `select_related` or `load()`.

Let's see an example.

**Create a user and a profile**

```python
user = await User.query.create(first_name="Foo", email="foo@bar.com")
await Profile.query.create(user=user)
```

**Accessing the user data from the profile**

```python
profile = await Profile.query.get(user__email="foo@bar.com")

print(profile.user.email) # "foo@bar.com"
print(profile.user.first_name) # "Foo"
```

## ForeignKey Constraints

As mentioned in the [foreign key field](./fields/index.md#foreignkey) documentation, you can specify constraints for foreign keys.

The available values are `CASCADE`, `SET_NULL`, and `RESTRICT`, which can be imported from `edgy`.

```python
from edgy import CASCADE, SET_NULL, RESTRICT
```

When defining a foreign key or one-to-one key, the `on_delete` parameter is **mandatory**.

Looking back at the previous example:

```python hl_lines="20"
{!> ../docs_src/relationships/model.py !}
```

The `Profile` model defines an `edgy.ForeignKey` to `User` with `on_delete=edgy.CASCADE`. This means that whenever a `User` is deleted, all associated `Profile` instances will also be removed.

### Delete Options

* **CASCADE**: Remove all referencing objects.
* **RESTRICT**: Restricts the removal of referenced objects.
* **PROTECT**: Like restrict but if the referenced object is deleted by other pathes still delete.
* **SET_NULL**: Sets the referencing instance's foreign key to `null` when the referenced object is deleted. When using `SET_NULL`, `null=True` must also be provided.
* **SET_DEFAULT**: Sets the referencing foreign key to its default.
* **DO_NOTHING**: Don't trigger anything.

## OneToOne

Creating a `OneToOneField` relationship between models is similar to [ForeignKey](#foreignkey), with the key difference being that it uses `unique=True` on the foreign key column.

```python hl_lines="20"
{!> ../docs_src/relationships/onetoone.py !}
```

The same rules apply to this field as to [ForeignKey](#foreignkey), as it derives from it.

Let's create a `User` and a `Profile`.

```python
user = await User.query.create(email="foo@bar.com")
await Profile.query.create(user=user)
```

Creating another `Profile` with the same user will fail and raise an exception.

```
await Profile.query.create(user=user)
```

## Special methods

The reverse end of many-to-many or ForeignKey behaves like the

[Operations of ManyToManyField](./queries/many-to-many.md#operations).

In fact the same intermediate relation protocol is used.

## Limitations

Edgy currently does not support cross-database queries.

This means you cannot join a MySQL table with a PostgreSQL table.

How can this be implemented?

Of course joins are not possible. The idea is to execute a query on the child database and then check which foreign key values match.

Of course the ForeignKey has no constraint and if the data vanish it points to nowhere.
