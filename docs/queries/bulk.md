# Bulk operations

Bulk operations are different from normal queryset operations.
They don't adher the `embed_parent` attribute by default (so they don't load nested objects) and are not necessarily
complete.

Why? Because they are optimized for performance. You can however provide `resolve_embed=True` to try to resolve. In case operations may fail with an `QuerySetError` when the values/objects provided/retrieved doesn't have all keys defined for loading (by default primary keys)
and can't load.

The returned array is in the same order as the values/objects provided. And contains for `bulk_get_or_create` and `bulk_update_or_create` a state flag if this object was created is added.

**Input**

Input for all bulk operations are models of the right type or dictionaries. They can be intermixed and must be provided in an `Iterable`.

## Operations

### Bulk create

When you need to create many instances in one go, or `in bulk`.

!!! Limitation
    In the database created primary keys can't be retrieved, so check if the returned objects
    are complete with `can_load`.

```python
returned_objs = await User.query.bulk_create([
    {"email": "foo@bar.com", "first_name": "Foo", "last_name": "Bar", "is_active": True},
    {"id": 100, "email": "bar@foo.com", "first_name": "Bar", "last_name": "Foo", "is_active": True},
])
assert not returned_objs[0].can_load  # the pks are incomplete
assert returned_objs[1].can_load  # the pks are complete
```

#### `ignore_conflicts`

When the database is compatible and we don't need the returned values, we can use `ignore_conflicts=True` instead `bulk_get_or_create`.
Assuming email is the primary key, we can do something like this:

```python
await User.query.bulk_create([
    {"email": "bar@foo.com", "first_name": "Bar", "last_name": "Foo", "is_active": True},
    ...
], ignore_conflicts=True)

# is ignored
await User.query.bulk_create([
    {"email": "bar@foo.com", "first_name": "Bar", "last_name": "Foo", "is_active": False},
    ...
], ignore_conflicts=True)
```

What does it do? Simply skipping rows which would cause a conflict. It is maybe not as performant because single inserts are issued.
Deduped objects are returned as `None` for `ignore_conflicts=True`.

### Bulk update

When you need to update many instances in one go, or **in bulk**. With `update_fields` you can define the fields updated.
By default all fields are updatable.

```python
await User.query.bulk_create([
    {"email": "foo@bar.com", "first_name": "Foo", "last_name": "Bar", "is_active": True},
    {"email": "bar@foo.com", "first_name": "Bar", "last_name": "Foo", "is_active": True},
])

users = await User.query.all()

for user in users:
    user.is_active = False

retrieved_objects = await User.query.bulk_update(users, update_fields=['is_active'])
```

!!! Note
    The old `fields` parameter for `update_fields` is still working but deprecated.

### Bulk Get or Create

When you need to perform in bulk a `get_or_create` in your models. The normal behavior would
be like the `bulk_create` but this bring an additional `unique_fields` where we can make sure
we do not insert duplicates by filtering the unique keys of the model data being inserted.
When not provided `unique_fields` default to the primary keys.

```python
results = await User.query.bulk_get_or_create([
    {"email": "foo@bar.com", "first_name": "Foo", "last_name": "Bar", "is_active": True},
    {"email": "bar@foo.com", "first_name": "Bar", "last_name": "Foo", "is_active": True},
], unique_fields=["email"])

# Try to reinsert the same values
await User.query.bulk_get_or_create([
    {"email": "foo@bar.com", "first_name": "Foo", "last_name": "Bar", "is_active": True},
    {"email": "bar@foo.com", "first_name": "Bar", "last_name": "Foo", "is_active": True},
], unique_fields=["email"])

users = await User.query.all() # 2 as total
```

!!! Note
    `bulk_get_or_create` fetches when using `unique_fields` all matching entries in a list.
    For reducing the amount searched, use something like `limit(100).bulk_get_or_create(..., unique_fields=[...])`.


### Bulk Update or Create

The returned array is in tuples with state flag if the object was created.

```python
results = await User.query.bulk_get_or_create([
    {"email": "foo@bar.com", "first_name": "Foo", "last_name": "Bar", "is_active": True},
    {"email": "bar@foo.com", "first_name": "Bar", "last_name": "Foo", "is_active": True},
], unique_fields=["email"])

assert results[0][1]  # created
assert results[0][1]  # created

# Try to reinsert the same values
results = await User.query.bulk_update_or_create([
    {"email": "foo@bar.com", "first_name": "Foo", "last_name": "Bar", "is_active": False},
    {"email": "bar@foo.com", "first_name": "Bar", "last_name": "Foo", "is_active": False},
], unique_fields=["email"], update_fields=["last_name"])

assert results[0][0].is_active
assert results[1][0].is_active
assert not results[0][1]  # updated
assert not results[1][1]  # updated

users = await User.query.all() # 2 as total
```

By default `unique_fields` are the primary keys and columns and `update_fields` are all the fields defined in the model class.
Note that `None` can be returned in case of input that doesn't contain enough information to generate an update (notably: the instance must be loadable).

#### What is the difference to `bulk_update`?

- It is possible to define `unique_fields`.
- It can create instances on the fly, not just update them.
- It can return `None` for instances which couldn't be inserted but have not enough information to generate an update.

## Advanced Topics

### `unique_fields`

`unique_fields` are explicit provided fields or database columns for deduplication. They are also used for the retrieval of instances.
Caching and deduplication only work if an input object has all `unique_fields` defined.
When left on `None` the primary keys and columns are used for `unique_fields`.

### `resolve_embed`

By default `embed_parent` isn't honored for bulk operations. If you need to resolve to embedded child when possible, you can specify
`embed_target=True`.
This mode has two effects:

- It is ensured that all returned instances `can_load` when `embed_parent` is active. If necessary, it will issue serialized single inserts.
- The embedding is resolved if `embed_parent` is set. You get the child with the embedded parent.

### loadable

An instances is loadable if its `can_load` property signals it is loadable. For dictionaries the on the fly generated instance is used.
But if you provide a correct instance you can do some tricks:

You can set the `identifying_db_fields` so a provided instance becomes suddenly loadable and for `bulk_update_or_create` the update succeeds instead returning `None`.
Other effects are that `resolve_embed` succeeds for such crafted instances.

It is planned to add signals so you will be able to manipulate the immediate instances via signals so you can do this trick also for dict inputs.
