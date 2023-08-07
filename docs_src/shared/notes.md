Edgy model declaration with `typing` is **merely visual**. The validations of the fields
are not done by the typing of the attribute of the models but from the **edgy fields**.

Which means you don't need to worry about the *wrong* typing as long as you declare the correct
field type.

So does that mean pydantic won't work if you don't declare the type? Absolutely not. Internally
Edgy runs those validations through the declared fields and the Pydantic validations are done
exactly in the same way you do a normal Pydantic model.

Nothing to worry about!

Let us see an example.

**With field typing**

```python
import edgy
from edgy import Database, Registry

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


class User(edgy.Model):
    """
    The User model to be created in the database as a table
    If no name is provided the in Meta class, it will generate
    a "users" table for you.
    """

    id: int = edgy.IntegerField(primary_key=True)
    is_active: bool = edgy.BooleanField(default=False)

    class Meta:
        registry = models
```

**Without field typing**

```python
import edgy
from edgy import Database, Registry

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


class User(edgy.Model):
    """
    The User model to be created in the database as a table
    If no name is provided the in Meta class, it will generate
    a "users" table for you.
    """

    id = edgy.IntegerField(primary_key=True)
    is_active = edgy.BooleanField(default=False)

    class Meta:
        registry = models
```

It does not matter if you type or not, Edgy knows what and how to validate via `edgy fields` like
`IntegerField` or `BooleanField` or any other field.
