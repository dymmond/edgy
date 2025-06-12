# Admin

## What is the admin feature?

This is an **experimental** Web-GUI to expose the database to the webbrowser.
Admins can use the GUI to fix some problems.

## Using Admin from cli

Use something like:

`edgy -admin_serve`

or **only** if you want to test the feature:

`edgy --app tests.cli.main admin_serve --create-all`

and watch the console output for an automic generated password. It is required for
accessing the admin. The default username is `admin`.

You can however customize them all via:

`edgy admin_serve --auth-name=edgy --auth-pw=123`

!!! Warning
    This only serves as an example. Please use stronger passwords! Your whole database is open this way!

!!! Warning
    Only use `--create-all` when not using migrations.

### Limitations

Despite this is a quite non-invasive way to use the admin feature, you have a quite limited
way of integration. There is no user management only a basic auth.
For more

## Embedding Admin

For embedding the admin you need a lilya session or something compatible (provide scope["session"] with a dict like interface).
You can either declare a global session or provide a `session_cookie` name to prevent collisions.

```python title="Global session"
{!> ../docs_src/admin/admin_embed.py !}
```

```python title="Different cookie"
{!> ../docs_src/admin/admin_embed_different_cookie.py !}
```

You can multiplex the session via `sub_path` (will probably land in lilya 0.15.5)

```python title="Multiplexed"
{!> ../docs_src/admin/admin_embed_multiplexed.py !}
```

## Excluding models

Just set in Meta, the flag `in_admin` to `False`. This flag is inherited.
If you just want to exclude models from the creation you can set `no_admin_create` to `True`.

Both flags can be just inherited by using a value of `None`. The default behaviour for `in_admin` (when nowhere in the hierarchy a value was set) is `True`.
For `no_admin_create` it is `False`.

Example:

By default `ContentType` is `in_admin` but `no_admin_create` is true, so we cannot create a new instance.

For m2m models `in_admin` defaults to false and `no_admin_create` to true.

We can however change this:

```python title="Creatable ContentType" hl_lines="11"

{!> ../docs_src/admin/admin_content_type.py !}
```

## Customizing model admins

One nice feature of edgy admin is the optional customization of the admin interface.

By default it doesn't care for user permissions but can be adapted to do so on a per model base.
Here it is quite unoppinionated. You can use every connection information you like for adding or removing fields.

For example the request.user when embedding the admin in a bigger application.

You can use user attributes or permissions (when used with a user setup) or simply check the connection.

```python title="Permission example"
{!> ../docs_src/admin/admin_permission.py !}
```

### Hooks in detail

- **get_admin_marshall_config(cls, *, phase, for_schema=False) -> dict:** - Customize quickly the marshall_config of the generated Marshall. Use this for excluding fields depending on the phase.
- **get_admin_marshall_class(cls, *, phase, for_schema=False) -> type[Marshall]** - Customize the whole marshall. This allows replacing the Marshall completely, adding some fields and other goodies.
- **get_admin_marshall_for_save(cls, instance= None, /, \*\*kwargs) -> Marshall** - Classmethod called for getting the final marshall to save. Kwargs contains all the kwargs provided by the extraction. You might can build some customization around the saving here.

Here an simpler example how to use this:

```python title="Basic customization example"
{!> ../docs_src/admin/admin_custom_admin_marshall.py !}
```

### Admin marshall phase and for_schema parameters

The `phase` parameter can contain following values:
- `list`: Marshall used for the model list representation in admin. Only for viewing.
- `view`: Marshall used for the model detail view representation in admin. Only for viewing.
- `create`: Marshall used for creating new model instances in admin (when saving). You may can remove some fields.
- `update`: Marshall used for updating model instances in admin (when saving). You may can remove some fields.

The `for_schema` parameter contains the information if the marshall is used for a json_schema or for validation. When used for a json_schema,
we change in model_config the parameter extra to `forbid` so no arbitary editors are shown.
