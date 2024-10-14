# Permissions

One of the most basic needs in the database world is permission handling. Some approaches work via
database users but this is neither portable nor has the flexibility of users which reside as a normal table.

## Permission objects

### Users

Users are the main entrypoint in nearly every application. Permissions require such a class. The class itself is referenced via
a ManyToMany field named `users`.

### Groups

Groups can be useful for organizing permissions in sets which can be applied to users. In the Permission template they are optional.
When used the Permission object needs a ManyToMany field named `groups`.

### Model names

Model names are a scope limiter for permssions. Instead of allowing e.g. users to edit everything they can only edit blogs. Like groups they are optional.
They are enabled via a CharField or TextField named `name_model`. Reason: pydantic occupies the `model_` prefix.
When not wanting an extra field and having only object related permissions you can also check model names against objects.

### Objects

Permissions can be directly assigned to object instances via ContentTypes. This is useful for per object permissions.
Again this feature is optional. However if `name_model` is not specified `model_names` are checked against the ContentType.
The feature can be enabled via a ForeignKey named `obj` to ContentType.

## How to use

Permission models detect automatically which features they have. This is why there are field names which are strictly enforced.

There are 3 extra manager methods:

- permissions_of(sources)
- users(...)
- groups(...)

### Parameters of users and groups

Except permissions all of the parameters are optional

- permissions (str/Sequence[str]) - Permission names.
- model_names (str/Sequence[str/None]) - Model names. Only available with `name_model` or `obj`.
- objects (Object/Sequence[Object/None]) - Objects permissions are tied to.
- include_null_model_name (Default: True) - When model_names are not None automatically add a check for a null model_name.
- include_null_object (Default: True) - When objects are not None automatically add a check for a null model_name.

Why the last ones? If you want to untie a Permission you can simply set `obj` or `name_model` to None and voila the Permission has now a broader scope.

## Quickstart

```python
{!> ../docs_src/permissions/quickstart.py !}
```

Despite not necessary it is recommended to use unique_together for the fields used to identify a Permission.

## Advanced

Here an advanced example with all possible fields set.

```python
{!> ../docs_src/permissions/advanced.py !}
```

## Advanced with primary keys

Edgy has a very flexible overwrite logic. Instead of using unique_together, following code is possible:


```python
{!> ../docs_src/permissions/primary_key.py !}
```

However permissions cannot change their scope this way and there is a little overhead because the primary keys are used for the foreign keys.

You can also just overwrite name with a primary key field. This way the implicit id is removed.
