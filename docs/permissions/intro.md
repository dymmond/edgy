# Permissions in Edgy

Managing permissions is a crucial aspect of database-driven applications.
Edgy provides a flexible and portable way to handle permissions, using database tables rather than relying solely on database users.
This feature is entirely composable in contrast to django, you can have full-fledged object-permissions to a simple user permission system
just by providing the fields.
It is up to you how to design e.g. the Group model. If it should have extra attributes or not.
You just need to keep the convention, some fields are mandatory to get the results wanted.

The permission system does **not** require ContentTypes. They are only required for per object permissions.

## Permission Objects

Edgy's permission system is designed to accommodate various permission structures. Here's a breakdown of the key components:

### Users

Users are the central entities in most applications. Permissions are typically associated with users through a ManyToMany field named `users`.

### Groups

Groups allow you to organize permissions into sets that can be assigned to users. This feature is optional, but if used, the permission model must include a ManyToMany field named `groups`.

### Model Names

Model names provide a way to scope permissions to specific models (e.g., blogs, articles). This feature is optional and is enabled by including a `CharField` or `TextField` named `name_model`.

**Note:** The `model_` prefix is reserved by Pydantic, so `name_model` is used instead. If you only need object-specific permissions, you can check model names against objects directly.

### Objects

Permissions can be assigned to specific object instances using ContentTypes, enabling per-object permissions. This is an optional feature. If `name_model` is not specified, permissions are checked against `model_names` in the ContentType.

To enable this, include a `ForeignKey` named `obj` that points to ContentType.

## Usage

Edgy's permission models automatically detect the features you've enabled based on the presence of specific fields. This is why strict field naming conventions are important.

Edgy provides three additional manager methods for working with permissions:

-   `permissions_of(sources)`
-   `users(...)`
-   `groups(...)`

### Parameters for `users` and `groups`

The `users` and `groups` methods accept the following parameters (except for `permissions`, all are optional):

-   `permissions` (str | Sequence[str]): The names of the permissions to check.
-   `model_names` (str | Sequence[str] | None): Model names, used if `name_model` or `obj` is present.
-   `objects` (Object | Sequence[Object] | None): Objects associated with the permissions.
-   `include_null_model_name` (bool, default: True): Automatically includes a check for a `null` model name when `model_names` is not `None`.
-   `include_null_object` (bool, default: True): Automatically includes a check for a `null` object when `objects` is not `None`.

### Why Include `include_null_model_name` and `include_null_object`?

Setting `obj` or `name_model` to `None` allows you to broaden the scope of a permission, making it applicable to all objects or models.

## Quickstart Example

Here's a basic example of a permission model:

```python
{!> ../docs_src/permissions/quickstart.py !}
```

It's recommended to use `unique_together` for the fields that uniquely identify a permission.

## Advanced Example

This example demonstrates a permission model with all possible fields configured:

```python
{!> ../docs_src/permissions/advanced.py !}
```

## Advanced Example with Primary Keys

Edgy's flexible overwrite logic allows you to use primary keys instead of `unique_together`:

```python
{!> ../docs_src/permissions/primary_key.py !}
```

Using primary keys in this way prevents permissions from changing their scope and introduces a slight overhead due to the use of primary keys as foreign keys.

Alternatively, you can overwrite `name` with a primary key field, which removes the implicit ID.

## Practical Example: Automating Permission Management

This example demonstrates how to create a `Permission` object class that automates permission assignment.

```python
{!> ../docs_src/permissions/example.py !}
```

This example shows how to automate permission management by consolidating permission-related logic in a single class. This allows you to create, manage, and revoke permissions efficiently.

**Note:** This example is for illustrative purposes and should be adapted to fit your specific application requirements.
