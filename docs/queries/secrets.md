# Secrets

Have you ever wished for a way to query the database and omit sensitive data without the hassle of filtering throughout your codebase? Your wish is granted.

The `secret` attribute is a special feature of [fields](../fields/index.md), available on each field. When set to `True`, and used in conjunction with `exclude_secrets`, it ensures that sensitive data is never returned.

In essence, it provides a safe way to expose your data.

## Exclude Secrets

How does this work in practice? It's quite simple. Set the `secret` attribute to `True`, and when you want to safely expose data via a query, call `exclude_secrets`.

**Rest assured, the `secret` attribute is not stored in the database in any way.**

Let's look at an example.

```python hl_lines="11"
{!> ../docs_src/queries/secrets/model.py !}
```

Notice the `password` field. It has the `secret` attribute set to `True`. This is beneficial because now we can query the database and retrieve records without worrying about leaking the `password` to the outside world.

We'll use a special method called `exclude_secrets`. This function returns a [queryset](./queries.md#queryset), allowing you to combine it with other operations as usual, but with the added benefit of not exposing secrets.

### `exclude_secrets`

This is the function that makes all the magic happen. Let's see how it's used.

The syntax is straightforward.

```python
Model.query.exclude_secrets()
```

#### Example

Let's create some data.

```python
await User.query.create(name="Edgy", email="edgy@example.dev", password="A@Pass123")
await User.query.create(name="Ravyn", email="ravyn@ravyn.dev", password="A@Pass321")
```

Now, let's query, excluding the secrets.

```python
await User.query.exclude_secrets()
```

This will return all users as a normal query would. Let's look at it more closely.

```python
user = await User.query.exclude_secrets(id=1)
```

This will return the user with `id=1`, which is named "Edgy". Now, let's see the full object details.

```python
user.model_dump()

{"id": 1, "name": "Edgy", "email": "edgy@example.com"}
```

As you can see, the `password` is not displayed at all. This is because the field has the `secret` attribute declared. This is especially useful when you don't want to manually filter and manipulate these details, and prefer to use standard ORM queries without any hassle.

#### Other Examples

As mentioned, you can combine operations with `exclude_secrets`.

```python
users = await User.query.filter(id=1).exclude_secrets()
users = await User.query.filter(id=1).exclude_secrets().get() # returns only 1 object
users = await User.query.exclude_secrets().only("email")
```

And so on.

### Make the Field Available

What if you want to expose fields that previously had the `secret` attribute declared?

There are a few ways to do this.

One way is by **not using the `exclude_secrets`** queryset. Another is by removing the `secret` flag from the field.

Removing the flag is fine, as you can add it back at any time. However, the best approach is to simply not call `exclude_secrets` at all. The `secret=True` flag is only used for that specific queryset, meaning it won't affect anything in your models.
