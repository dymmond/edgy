# Extras

This section refers to the extras that Edgy offer and can be used in your application without
incurring into extra overhead to make it happen.

If you are in this section, you surely read about the [auto discovery](./migrations/discovery.md)
and how it relates with the way Edgy handles and manages migrations for you.

But, what if you simply would like to use the [shell](./shell.md) or any related command offered
by Edgy that doesn't necessarily requires migration management?

The Migrate object is the way of Edgy knowing what to do and how to manage your models but there
are cases where that doesn't happen and it is not needed, for example,
**a project using [reflect models](./reflection/reflection.md)**.

A project using reflect models, means that somehow migrations are managed externally and not by
Edgy and Edgy only needs to reflect those tables back into your code, so, do you really need
the **Migrate** object here? **Short answer is no**.

So how can you still use those features without depending on the Migrate object? Enters
[EdgyExtra](#edgyextra).

## EdgyExtra

This is the object you want to use when **you don't need Edgy to manage the migrations for you**
and yet still being able to use Edgy tools like the [shell](./shell.md).


### How does it work

Well, its actually very similar to Migrate object in terms of setup.

Let us use [Esmerald](https://esmerald.dev) again as an example like we did for the
[tips and tricks](./tips-and-tricks.md).

```python hl_lines="12 47"
{!> ../docs_src/extras/app.py !}
```

And that is it, you can use any tool that does not relate with migrations in your application.

!!! Warning
    Be aware of the use of this special class in production! It is advised not to use it there.

## Migrate multiple schemes

Migrate has a special parameter named `multi_schema`. It can be a boolean, a string, a regex pattern.
When set to a value different False (the default) models will be migrated in multiple schemes not only the main schema.

When setting to True, all found schemes are evaluated. By providing a string or regex, you can filter the schemes via regex. There
are also other keywords which are passed through the MigrationContext of alembic.

For excluding system schemes there is a second parameter named: `ignore_schema_pattern`. It defaults to `information_schema`.
Set to `None` to deactivate it.

## Note

For now, besides the migrations and the shell, Edgy does not offer any extra tools but there are
plans to add more extras in the future and `EdgyExtra` is the way to go for that setup.
