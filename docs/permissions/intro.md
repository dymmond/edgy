# Permissions

Handling permissions is one of the fundamental needs in the database world. Some approaches rely on database users, but this method lacks portability and the flexibility of managing users as a standard database table.

## Permission Objects

### Users

Users serve as the primary entry point in most applications. Permissions require a user-related class, which is referenced via a ManyToMany field named `users`.

### Groups

Groups help organize permissions into sets that can be applied to users. In the permission model, groups are optional. When used, the permission object must include a ManyToMany field named `groups`.

### Model Names

Model names serve as scope limiters for permissions. Instead of granting users unrestricted access, they can be restricted to specific models, such as blogs. Like groups, this feature is optional.

Model names are enabled using a `CharField` or `TextField` named `name_model`. This naming convention is necessary because Pydantic reserves the `model_` prefix. If you only require object-specific permissions and do not want an additional field, you can check model names against objects instead.

### Objects

Permissions can be assigned directly to specific object instances via ContentTypes, enabling per-object permissions. This feature is optional. However, if `name_model` is not specified, permissions are checked against `model_names` in the ContentType.

To enable this feature, include a `ForeignKey` named `obj` pointing to ContentType.

## Usage

Permission models automatically detect their available features. This is why certain field names are strictly enforced.

There are three additional manager methods:

- `permissions_of(sources)`
- `users(...)`
- `groups(...)`

### Parameters for `users` and `groups`

Except for `permissions`, all parameters are optional:

- `permissions` (str | Sequence[str]) – The names of the permissions.
- `model_names` (str | Sequence[str] | None) – Model names, available only if `name_model` or `obj` is present.
- `objects` (Object | Sequence[Object] | None) – Objects associated with permissions.
- `include_null_model_name` (bool, default: True) – When `model_names` is not `None`, automatically adds a check for a `null` model name.
- `include_null_object` (bool, default: True) – When `objects` is not `None`, automatically adds a check for a `null` model name.

### Why Include `include_null_model_name` and `include_null_object`?

If you want to broaden the scope of a permission, you can set `obj` or `name_model` to `None`, effectively untethering the permission from specific objects or models.

## Quickstart

```python
{!> ../docs_src/permissions/quickstart.py !}
```

Although not strictly necessary, it is recommended to use `unique_together` for the fields that identify a Permission.

## Advanced

Here is an advanced example with all possible fields configured.

```python
{!> ../docs_src/permissions/advanced.py !}
```

## Advanced with primary keys

Edgy has highly flexible overwrite logic. Instead of using `unique_together`, the following code can be used:

```python
{!> ../docs_src/permissions/primary_key.py !}
```

However, permissions cannot change their scope this way, and there is a slight overhead since primary keys are used for foreign keys.

Alternatively, you can overwrite `name` with a primary key field, which removes the implicit ID.

## Pratical example

This is for explanatory reasons and the code **must** be changed to fit your needs, so let us simply imagine
we want to build a `Permission` object class that manages the `assign_permissions` for you.

You could do something like this:

```python
{!> ../docs_src/permissions/example.py !}
```

The above example doesn't mean you should blindly copy but offers a simple idea how you could automate
your permissions by unifying in one place.

This allows you to create permissions in bulk or simply simple permissions as well as revoke them
if necessary.

Do you need this? Probably not but its just an example.
