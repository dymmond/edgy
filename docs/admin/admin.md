# Admin

## What is the admin feature?

This is an **experimental** Web-GUI to expose the database for the webbrowser.
Admins can use the GUI to fix some problems.

!!! Warning
    Currently you are responsible for securing the powerful admin. Never expose to untrusted parties.

## Using Admin from cli

Use something like:

`edgy --app tests.cli.main admin_serve --create-all`

!!! Warning
    Never expose to 0.0.0.0. We have no security as well as user permission management yet. So it is highly recommended
    to protect the admin interface by including it in your project.


## Embedding Admin

See edgy/cli/operations/admin_serve.py to get an idea.


## Excluding models

Just set in Meta, the flag `in_admin` to `False`. This flag is inherited.
