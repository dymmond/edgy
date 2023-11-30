# Secrets

Was there a time where you wished you could have a way of querying the database and not returning
some sentive data without the hassle of filtering all over the codebase? Well, say no more.

The `secret` is a special attribute of the [fields](../fields.md) that is available on each field
that basically if set to `True` and using the `exclude_secrets` will make sure it will never
return any sensitive data.

In other words, it will safely expose your data.

## Exclude Secrets

How does this work in reality? Well, very simple actually. You will need to set the `secret`
attribute to `True` and when you want to safely expose the data via query, call the `exclude_secrets`.

**No worries, the `secret` attribute is not stored in the database in any way**.

Let us see an example.

```python hl_lines="11"
{!> ../docs_src/queries/secrets/model.py !}
```

Check the `password` field. That same field has the `secret` set to `True` and this is great because
now we want to query the database and get some records without worrying about leaking the `password`
to the outside world.

For this we will be using a special method called `exclude_secrets`. This function also returns a
[queryset](./queries.md#queryset) which means you can mix with any other operation as per normal
usage but with the plus of not exposing the secrets.

### exclude_secrets

This is the special function that allows all the magic to happen. Let us see how it would look
like if we were using it.

The syntax is very simple.

```python
Model.query.exclude_secrets()
```

#### Example

Let us create some data.

```python
await User.query.create(name="Edgy", email="edgy@example.dev", password="A@Pass123")
await User.query.create(name="Esmerald", email="esmerald@esmerald.dev", password="A@Pass321")
```

Now, let us query excluding the secrets.

```python
await User.query.exclude_secrets()
```

This will return all the users as per normal query but let us see more in detail.

```python
user = await User.query.exclude_secrets(id=1)
```

This will return the user with `id=1` which is the name `Edgy`. Now, let us see how it would look
like seeing all the details of the object.

```python
user.model_dump()

{"id": 1, "name": "Edgy", "email": "edgy@example.com"}
```

As you can see, there is no `password` being displayed at all and that is because the field has
the `secret` declared. This can be specially useful if you don't want to be bother to filter and
manipulate all of those details manually and simlpy still using the normal ORM queries without any
hassle.

#### Other examples

As mentioned before, you can mix the operations with the `exclude_secrets` which means you can do
things like this.

```python
users = await User.query.filter(id=1).exclude_secrets()
users = await User.query.filter(id=1).exclude_secrets().get() # returns only 1 object
users = await User.query.exclude_secrets().only("email")
```

And the list goes on and on.

### Make the field available

What if you want to expose the fields that previously had the `secret` declared?

There are different ways of making this happen.

One of the ways is by **not using the exclude_secrets** queryset and the other is by removing the
flag `secret` from the field.

Removing the flag has no issue since you can add it back at any given time but the best way it would
be by simply not calling `exclude_secrets` at all since the flag `secret=True` is only used for that
given queryset which also means it won't impact anything in your models.
