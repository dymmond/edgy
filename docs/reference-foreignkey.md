# Reference ForeignKey (RefForeignKey)

The `Reference ForeignKey` (RefForeignKey) is a unique feature in **Edgy** that simplifies the creation of related records.

## What is a Reference ForeignKey?

Unlike a standard [ForeignKey](./fields/index.md#foreignkey), a `RefForeignKey` does **not** create a foreign key constraint in the database. Instead, it acts as a mapper that facilitates automated record insertion.

!!! Warning
    `RefForeignKey` is **only** used for inserting records, not updating them. Exercise caution to avoid creating duplicates.

`RefForeignKey` **always creates** new records, even on `save()`, rather than updating existing ones.

## Brief Explanation

To use `RefForeignKey`, you'll need a [ModelRef](#modelref).

[ModelRef](#modelref) is an Edgy object that enables interaction with the declared model and performs operations.

**Scenario Example**

Consider a blog with `users` and `posts`:

```python
{!> ../docs_src/reffk/example1.py !}
```

Typically, you'd create `users` and `posts` like this:

```python
# Create the user
user = await User.query.create(name="Edgy")

# Create posts and associate with the user
await Post.query.create(user=user, comment="A comment")
await Post.query.create(user=user, comment="Another comment")
await Post.query.create(user=user, comment="A third comment")
```

`RefForeignKey` offers an alternative approach.

## RefForeignKey

`RefForeignKey` is internally treated as a **list of the model declared in [ModelRef](#modelref)**.

Import it:

```python
from edgy import RefForeignKey
```

Or

```python
from edgy.core.db.fields import RefForeignKey
```

`RefForeignKey` requires the `to` parameter to be a `ModelRef` object; otherwise, it raises a `ModelReferenceError`.

### Parameters

* **to:** The [ModelRef](#modelref) to point to.
* **null:** Whether to allow nulls when creating a model instance.

    !!! Warning
        This applies during instance creation, not saving. It performs Pydantic validations.

## ModelRef

`ModelRef` is a special Edgy object for interacting with `RefForeignKey`.

```python
from edgy import ModelRef
```

Or

```python
from edgy.core.db.models import ModelRef
```

`ModelRef` requires the `__related_name__` attribute to be populated; otherwise, it raises a `ModelReferenceError`.

`__related_name__` should point to a Relation (reverse side of ForeignKey or ManyToMany relation).

`ModelRef` is a Pydantic `BaseModel`, allowing you to use Pydantic features like `field_validator` and `model_validator`.

### Attention

When declaring `ModelRef` fields, ensure they align with the `__related_name__` model's constraints and uniques.

You cannot cross multiple models (except the through model in ManyToMany).

### Declaring a ModelRef

Declare the `__related_name__` field and specify the fields for instantiation.

**Example:**

```python title="The original model"
{!> ../docs_src/reffk/model_ref/how_to_declare.py !}
```

Create a model reference:

```python title="The model reference" hl_lines="9-10"
{!> ../docs_src/reffk/model_ref/model_ref.py !}
```

Or:

```python title="The model reference" hl_lines="19-20"
{!> ../docs_src/reffk/model_ref/model_ref2.py !}
```

Include at least the non-null fields of the referenced model.

## How to Use

Combine `RefForeignKey` and `ModelRef` in your models.

**Scenario Example (Revisited)**

```python
{!> ../docs_src/reffk/example1.py !}
```

Use `RefForeignKey` instead:

### In a Nutshell

```python hl_lines="10-12 18"
{!> ../docs_src/reffk/nutshell.py !}
```

Declare the `ModelRef` for the `Post` model and pass it to the `posts` field of the `User` model.

!!! Note
    `RefForeignKey` does **not** create a database field. It's for internal Edgy model purposes.

### More Structured

Separate references into a `references.py` file:

```python hl_lines="5" title="references.py"
{!> ../docs_src/reffk/references.py !}
```

Models with imports:

```python hl_lines="6 15" title="models.py"
{!> ../docs_src/reffk/complex_example.py !}
```

Using ModelRefs without RefForeignKey:

```python title="models.py"
{!> ../docs_src/reffk/positional_example.py !}
```

### Writing Results

Adapt the insertion method from the scenario:

**Old Way:**

```python
# Create the user
user = await User.query.create(name="Edgy")

# Create posts and associate with the user
await Post.query.create(user=user, comment="A comment")
await Post.query.create(user=user, comment="Another comment")
await Post.query.create(user=user, comment="A third comment")
```

**Using ModelRef:**

```python
# Create the posts using PostRef model
post1 = PostRef(comment="A comment")
post2 = PostRef(comment="Another comment")
post3 = PostRef(comment="A third comment")

# Create the usee with all the posts
await User.query.create(name="Edgy", posts=[post1, post2, post3])
# or positional (Note: because posts has not null=True, we need still to provide the argument)
await User.query.create(post1, post2, post3, name="Edgy", posts=[])
```

This ensures proper object creation and association.

## Using in API

Use `RefForeignKey` as a nested object in your API.

### Declare Models, Views, and ModelRef

```python title="app.py"
{!> ../docs_src/reffk/apis/complex_example.py !}
```

### Making the API Call

```python
{!> ../docs_src/reffk/apis/api_call.py !}
```

**Response:**

```json
{
    "name": "Edgy",
    "email": "edgy@ravyn.dev",
    "language": "EN",
    "description": "A description",
    "comment": "A COMMENT",
    "total_posts": 4,
}
```

#### Errors

Pydantic validations apply:

```json
{
    "name": "Edgy",
    "email": "edgy@ravyn.dev",
    "language": "EN",
    "description": "A description"
}
```

Response:

```json
{
    "type": "missing",
    "loc": ["posts"],
    "msg": "Field required",
    "input": {
        "name": "Edgy",
        "email": "edgy@ravyn.dev",
        "language": "EN",
        "description": "A description",
    },
}
```

##### Wrong Type

`RefForeignKey` expects a list:

```json
{
    "type": "item_type",
    "loc": ["posts"],
    "msg": "Input should be a valid list",
    "input": {"comment": "A comment"},
}
```

## Conclusion

`RefForeignKey` and `ModelRef` simplify database record insertion, especially in APIs.
