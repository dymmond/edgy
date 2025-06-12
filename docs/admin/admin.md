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

See edgy/cli/operations/admin_serve.py to get an idea.


## Excluding models

Just set in Meta, the flag `in_admin` to `False`. This flag is inherited.
If you just want to exclude models from the creation you can set `no_admin_create` to `True`.

Both flags can be just inherited by using a value of `None`. The default behaviour for `in_admin` (when in the hierarchy nowhere was t)
is True


## Customizing model admins

TODO: reference docs_src

### Hooks

- **get_admin_marshall_class(phase, for_schema=False) -> type[Marshall]** - Customize the fields seen when editing/creating a new model instance by customizing the marshall returned or replace it at all.

### `get_admin_marshall_class` phases

- `list`: Marshall used for the model list representation in admin. Only for viewing.
- `view`: Marshall used for the model detail view representation in admin. Only for viewing.
- `create`: Marshall used for creating new model instances in admin (when saving). You may can remove some fields you dislike.
- `update`: Marshall used for updating model instances in admin (when saving). You may can remove some fields you dislike.

There is also the parameter for_schema which allows to differ if it is for the schema rendering or the validation.
