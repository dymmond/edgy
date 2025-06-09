# Admin

## What is the admin feature?

This is an **experimental** Web-GUI to expose the database for the webbrowser.
Admins can use the GUI to fix some problems.

!!! Warning
    Currently you are responsible for securing the powerful admin. Never expose to untrusted parties.

## Using Admin from cli

Use something like:

`edgy --app tests.cli.main admin_serve --create-all`

and watch the console output for an automic generated password. It is required for
accessing the admin. The default username is "admin".

You can however customize them all via:

`edgy --app tests.cli.main admin_serve --create-all --auth-name=edgy --auth-pw=123`

!!! Warning
    This only serves as an example. Please use stronger passwords! Your whole database is open this way!



## Embedding Admin

See edgy/cli/operations/admin_serve.py to get an idea.


## Excluding models

Just set in Meta, the flag `in_admin` to `False`. This flag is inherited.


## Hooks

- **get_admin_marshall_class(phase, for_schema=False) -> type[Marshall]** - Customize the fields seen when editing/creating a new model instance by customizing the marshall returned or replace it at all.

### `get_admin_marshall_class` phases

- `view`: Marshall used for the model view representation in admin.
- `create`: Marshall used for creating new model instances in admin (when saving). You may can remove some fields you dislike.
- `update`: Marshall used for updating model instances in admin (when saving). You may can remove some fields you dislike.

There is also the parameter for_schema which allows to differ if it is for the schema rendering or the validation.
