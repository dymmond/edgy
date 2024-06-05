This is the part that makes a whole difference if you are thinking about querying a specific
database using a diffent [connection](https://edgy.dymmond.com/connection).

What does that even mean? Imagine you have a main database `public` (default) and a database copy somewhere
else called `alternative` (or whatever name you choose) and both have the model `User`.

You now want to query the `alternative` to gather some user data that was specifically stored
in that database where the connection string is different.

The way **Edgy** operates is by checking if that alternative connection exists in the `extra`
parameter of the registry and then uses that connection to connect and query to the desired database.

!!! Warning
    To use the `alternative` database, the connection **must be declared** in the `registry` of the
    model or else it will raise an `AssertationError`.

The way of doing that is by using the `using_with_db` of the queryset. This is particularly useful
if you want to do some tenant applications or simply
connecting to a different database to gather your data.

Simple right?

Nothing like a good example to simplify those possible confusing thoughts.

Let us assume we want to `bulk_create` some users in the
`alternative` database instead of the `default`.

```python hl_lines="6-7"
{!> ../docs_src/registry/extra/declaration.py !}
```

As you can see, the `alternative` was declared in the `extra` parameter of the `registry` of the
model **as required**.

Now we can simply use that connection and create the data in the `alternative` database.

```python hl_lines="23"
{!> ../docs_src/registry/extra/create.py !}
```

Did you notice the `alternative` name in the `using_with_db`? Well, that **should match** the name
given in the `extra` declaration of the registry.

**You can have as many connections declared in the extra as you want, there are no limits.**
