# Reference ForeignKey

This is so special and unique to **Edgy** and rarely seen (if ever) that deserves its own page in
the documentation!

## What is a Reference ForeignKey

Well for start it is not a normal [ForeignKey](./fields.md#foreignkey). The reason why calling
**RefForeignKey** it is because of its own unique type of functionality and what it can provide
when it comes to **insert** records in the database.

This object **does not create** any foreign key in the database for you, mostly because this type
literally does not exist. Instead if some sort of a mapper that can coexist inside your [model][models]
declaration and help you with some automated tasks.

!!! Warning
    The [RefForeignKey][reffk] its only used for insertion of records and not for updates.
    Be very careful not to create duplicates and make those normal mistakes.

As mentioned above, `RefForeignKey` will **always create** (even on `save()`) records, it won't
update if they exist.

## Brief explanation

In a nutshell, to use the [RefForeignKey][reffk] you will need to use a [ModelRef][model_ref].

The [ModelRef][model_ref] is a special Edgy object that will make sure you can interact with the
model declared and perform the operations.

Now, what is this useful? Let us imagine the following scenario:

### Scenario example

You want to create a blog or anything that has `users` and `posts`. Something like this:

```python
{!> ../docs_src/reffk/example1.py !}
```

Quite simple so far. Now the normal way of creating `users` and `posts` would be like this:

```python
# Create the user
user = await User.query.create(name="Edgy")

# Create posts and associate with the user
await Post.query.create(user=user, comment="A comment")
await Post.query.create(user=user, comment="Another comment")
await Post.query.create(user=user, comment="A third comment")
```

Simple, right? What if there was another way of doing this? This is where the [RefForeignKey][reffk] gets in.
## RefForeignKey

A RefForeignKey is internally interpreted as a **list of the model declared in the [ModelRef][model_ref]**.

How to import it:

```python
from edgy import RefForeignKey
```

Or

```python
from edgy.core.db.fields import RefForeignKey
```

When using the `RefForeignKey` it make it **mandatory** to populate the `to` with a `ModelRef` type
of object or it will raise a `ModelReferenceError`.

### Parameters

* **to** - To which [ModelRef][model_ref] it should point.
* **null** - If the RefForeignKey should allow nulls when an instance of your model is created.

    !!! Warning
        This is for when an instance is created, **not saved**, which means it will run the normal
        Pydantic validations upon the creation of the object.

### ModelRef

This is another special type of object unique to **Edgy**. It is what allows you to interact with
the [RefForeignKey][reffk] and use it properly.

```python
from edgy import ModelRef
```

Or

```python
from edgy.core.db.models import ModelRef
```

The `ModelRef` when creating and declaring it makes it **mandatory** to populate the `__model__`
attribute or else it won't know what to do and it will raise a `ModelReferenceError`. This is good,
means you can't miss it even if you wanted to.

The `__model__` attribute can be the [model][models] itself or a string model name.

The `ModelRef` is a special type from the Pydantic `BaseModel` which means you can take advantage
of everything that Pydantic can do for you, for example the `field_validator` or `model_validator`
or anything you could normally use with a normal Pydantic model.

#### Attention

You need to be careful when declaring the fields of the `ModelRef` because that will be used to
against the `__model__` declared. If the [model][models] has `constraints`, `uniques` and so on
you will need to respect it when you are about to insert in the database.

#### Declaring a ModelRef

When creating a `ModelRef`, as mentioned before, you need to declare the `__model__` field pointing
to the [models][models] you want that reference to be.

Let us be honest, would just creating the `__model__` be enough for what we want to achieve? No.

In the `ModelRef` you **must** also specify the fields you want to have upon the instantiation of
that model.

Let us see an example how to declare the [ModelRef][model_ref] for a specific [model][models].

```python title="The original model"
{!> ../docs_src/reffk/model_ref/how_to_declare.py !}
```

First we have a model already created which is the database table represenation as per normal design,
then we can create a model reference for that same [model][models].

```python title="The model reference" hl_lines="9-10"
{!> ../docs_src/reffk/model_ref/model_ref.py !}
```

Or if you want to have everything in one place.

```python title="The model reference" hl_lines="19-20"
{!> ../docs_src/reffk/model_ref/model_ref2.py !}
```

The reason why the `__model__` accepts both types as value it is because a lot of times you will
**want to separate database models from model references** in different places of your codebase.

Another way of thinking *what fields should I put in the ModelRef* is:

> What minimum fields would I need to create a object of type X using the ModelRef?

This usually means, **you should put at least the not null fields** of the model you are referencing.

## How to use

Well, now that we talked about the [RefForeignKey][reffk] and the [ModelRef][model_ref], it is time
to see exactly how to use both in your models and to take advantage.

Do you remember the [scenario](#scenario-example) above? If not, no worries, let us see it again.

```python
{!> ../docs_src/reffk/example1.py !}
```

In the [scenario](#scenario-example) above we also showed how to insert and associate the posts with
the user but now it is time to use the [RefForeignKey][reffk] instead.

**What do we needed**:

1. The [RefForeignKey][reffk] field.
2. The [ModelRef][model_ref] object.

Now it is time to readapt the [scenario](#scenario-example) example to adopt the [RefForeignKey](#refforeignkey)
instead.

### In a nutshell


```python hl_lines="10-12 18"
{!> ../docs_src/reffk/nutshell.py !}
```

That is it, you simply declare the [ModelRef][model_ref] created for the `Post` model and pass it
to the `posts` of the `User` model inside the [RefForeignKey][reffk]. In our example, the `posts`
is **not null**.

!!! Note
    As mentioned before, the [RefForeignKey](#refforeignkey) **does not create** a field in the
    database. This is for internal Edgy model purposes only.

### More structured

The previous example has everything in one place but 99% of times you will want to have the references
somewhere else and just import them. A dedicated `references.py` file for instance.

With this idea in mind, now it kinda makes a bit more sense doesn't it? Someting like this:

```python hl_lines="5" title="references.py"
{!> ../docs_src/reffk/references.py !}
```

And the models with the imports.

```python hl_lines="6 15" title="models.py"
{!> ../docs_src/reffk/complex_example.py !}
```

### Writing the results

Now that we refactored the code to have the [ModelRef][model_ref] we will also readapt the way we
insert in the database from the [scenario](#scenario-example).

**Old way**

```python
# Create the user
user = await User.query.create(name="Edgy")

# Create posts and associate with the user
await Post.query.create(user=user, comment="A comment")
await Post.query.create(user=user, comment="Another comment")
await Post.query.create(user=user, comment="A third comment")
```

**Using the ModelRef**

```python
# Create the posts using PostRef model
post1 = PostRef(comment="A comment")
post2 = PostRef(comment="Another comment")
post3 = PostRef(comment="A third comment")

# Create the usee with all the posts
await User.query.create(name="Edgy", post=[post1, post2, post3])
```

This will now will make sure that creates all the proper objects and associated IDs in the corresponding
order, first the `user` followed by the `post` and associates that user with the created `post`
automatically.

Ok, this is great and practical sure but coding wise, it is also very similar to the original way,
right? Yes and no.

What if we were to apply the [ModelRef][model_ref] and the [RefForeignKey][reffk] in a proper API
call? Now, that would be interesting to see wouldn't it?

## Using in API

As per almost everything in the documentation, **Edgy** will use [Esmerald][esmerald] as an example.
Let us see the advantage of using this new approach directly there and enjoy.

You can see the [RefForeignKey][reffk] as some sort of ***nested*** object.

### Declare the models, views and ModelRef

Let us create the models, views and ModelRef for our `/create` API to use.


```python title="app.py"
{!> ../docs_src/reffk/apis/complex_example.py !}
```

See that we are adding some extra information in the response of our `/create` API just to make
sure you can then check the results accordingly.

### Making the API call

Now that we have everything in place, its time to create a `user` and at the same time create some
`posts` directly.

```python
{!> ../docs_src/reffk/apis/api_call.py !}
```

Now this is a beauty, isn't it? Now we can see the advantage of having the ModelRef. The API call
it is so much cleaner and simple and nested that one API makes it all.

**The response**

The if you check the response, you should see something similar to this.

```json
{
    "name": "Edgy",
    "email": "edgy@esmerald.dev",
    "language": "EN",
    "description": "A description",
    "comment": "A COMMENT",
    "total_posts": 4,
}
```

Remember adding the `comment` and `total_posts`? Well this is why, just to confirm the total inserted
and the comment of the first inserted,

#### Errors

As per normal Pydantic validations, if you send the wrong payload, it will raise the corresponding
errors, for example:

```json
{
    "name": "Edgy",
    "email": "edgy@esmerald.dev",
    "language": "EN",
    "description": "A description"
}
```

This will raise a `ValidationError` as the `posts` are **not null**, as expected and you should
have something similar to this as response:

```json
{
    "type": "missing",
    "loc": ["posts"],
    "msg": "Field required",
    "input": {
        "name": "Edgy",
        "email": "edgy@esmerald.dev",
        "language": "EN",
        "description": "A description",
    },
}
```

##### Sending the wrong type

The [RefForeignKey][reffk] is **always expecting a list** to be sent, if you try to send the wrong
type, it will raise a `ValidationError`, something similar to this:

**If we have sent a dictionary instead of a list**

```json
{
    "type": "list_type",
    "loc": ["posts"],
    "msg": "Input should be a valid list",
    "input": {"comment": "A comment"},
}
```

## Conclusion

This is an extensive document just for one field type but it deserves as it is complex and allows
you to simplify a lot your code when you want to **insert** records in the database all in one go.


[models]: ./models.md
[reffk]: #refforeignkey
[model_ref]: #modelref
[esmerald]: https://esmerald.dev
