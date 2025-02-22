# Related Name

**Edgy** offers a high degree of flexibility in how you define your models and execute queries.

A common practice involves declaring [ForeignKeys][foreign_keys] to establish [relationships][relationships] between tables.

A frequent scenario is the need to perform a "reverse query."

## What is a Related Name?

A related name is an attribute declared within [ForeignKeys][foreign_keys] that specifies the name of the reverse relation from the related model back to the model defining the relation.

It designates the attribute name used to access the related model from the opposite side of the relation.

Confused? Let's clarify with an example.

### How it Works

#### `related_name` Attribute

There are two approaches to using `related_name`.

##### Explicit Parameter

The related name can be directly declared within the [ForeignKeys][foreign_keys] `related_name` attribute, explicitly specifying the desired name.

##### Automatic Generation

Alternatively, if a `related_name` is not specified in the [ForeignKeys][foreign_keys], **Edgy** will **automatically generate the name** using the following format:

```text
<table-name>s_set
```

for non-unique relations, and

```text
<table-name>
```

for unique relations.

Edgy will use the lowercase model name of the related model to create the reverse relation.

For instance, consider a `Team` model with a [ForeignKey][foreign_keys] to an `Organisation` model.

```python title="models.py" hl_lines="16"
{!> ../docs_src/queries/related_name/example.py !}
```

Since no `related_name` was provided, **Edgy** will automatically assign the name **`organisations_set`**.

#### Deep Dive into `related_name`

Let's create three models:

* Organisation
* Team
* Member

```python title="models.py" hl_lines="16 24-27"
{!> ../docs_src/queries/related_name/models.py !}
```

We have declared three models with three [ForeignKeys][foreign_keys]:

* `org`: ForeignKey from `Team` to `Organisation`.
* `team`: ForeignKey from `Member` to `Team`.
* `second_team`: Another ForeignKey from `Member` to `Team`.

Now, let's populate the models with data.

```python
{!> ../docs_src/queries/related_name/data.py !}
```

We can now begin querying using `related_name`.

##### Querying with `related_name`

* **Retrieve all teams belonging to the `acme` organization.**

```python
teams = await acme.teams_set.all()

# [<Team: Team(id=1)>, <Team: Team(id=2)>, <Team: Team(id=3)>]
```

!!! Warning
    Because the `org` foreign key in the `Team` model lacked a `related_name`, Edgy automatically generated `teams_set`, accessible from `Organisation`. Refer to [default behavior](#auto-generating) for more information.

* **Find the team to which the members of the `blue_team` belong.**

```python
teams = await acme.teams_set.filter(members=blue_team).get()

# <Team: Team(id=2)>
```

**Nested Traversal Queries**

Notice the use of `members`? It's another reverse query linking the `Member` model to `Team`.

This illustrates how to perform nested and traversal queries across your models.

Let's explore further examples.

* **Determine the team to which `charlie` belongs.**

```python
team = await acme.teams_set.filter(members__email=charlie.email).get()

# <Team: Team(id=1)>
```

Again, we use the `members` related name, declared in the `Member` model as a [ForeignKey][foreign_keys] to `Team`, and filter by `email`.

##### Nested Queries

This is where it gets interesting. What if you need to perform deeper nested queries?

Let's add two more models:

* User
* Profile

!!! Warning
    These are used for illustrative purposes and may not represent optimal model design.

Our models now look like this:

```python title="models.py" hl_lines="38-40 47"
{!> ../docs_src/queries/related_name/new_models.py !}
```

We have added two more foreign keys:

* `member`: ForeignKey from `User` to `Member`.
* `user`: ForeignKey from `Profile` to `User`.

And their corresponding **related names**:

* `users`: Related name for the `User` foreign key.
* `profiles`: Related name for the `Profile` foreign key.

Let's populate the database with data.

```python hl_lines="16-17"
{!> ../docs_src/queries/related_name/new_data.py !}
```

This setup is sufficient to illustrate deep nested queries.

* **Find the team to which `monica` belongs, and verify the user's name.**

```python
team = await acme.teams_set.filter(
        members__email=monica.email, members__users__name=user.name
).get()

# <Team: Team(id=4)>
```

As expected, `monica` belongs to `green_team`, which has `id=4`.

* **Find the team to which `monica` belongs, verifying the email, user name, and profile type.**

```python
team = await acme.teams_set.filter(
    members__email=monica.email,
    members__users__name=user.name,
    members__users__profiles__profile_type=profile.profile_type,
)

# <Team: Team(id=4)>
```

Perfect! We have the expected results.

While this model design might not be ideal for production, it demonstrates the depth achievable with related name reverse queries.

[relationships]: ../relationships.md
[fields]: ../fields/index.md
[foreign_keys]: ../fields/index.md#foreignkey
