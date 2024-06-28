# Related Name

**Edgy** is very flexible in the way you assemble your models and perform your queries.

One very common example is declaring [ForeignKeys][foreign_keys] pointing it out to
declared [relationships][relationships] among tables.

One situation that happens very often is the one where you would like to do the `reverse query`.

## What is the related name

Related name is an attribute that can be declared inside the [ForeignKeys][foreign_keys]
and can be used to specify the name of the reverse relation from the related model back to the
model that defines the relation.

It is used to speficy the name of the attribute that can be used to access the related model from
the reverse side of the relation.

Confusing? Nothing like a good example to clear the things out.

### How does it work

#### related_name attribute

There are two ways of working with the `related_name`.

##### The parameter

The related name can be declared directly inside the [ForeignKeys][foreign_keys]
`related_name` attribute where you specify explicitly which name you want to use.

##### Auto generating

This is the other automatic way. When a `related_name` is not specified in the
[ForeignKeys][foreign_keys], **Edgy** will **automatically generate the name for you** with the
the following format:

```text
<table-name>s_set
```

when non-unique. And

```text
<table-name>
```

when unique.

Edgy will use the lowercased model name of the related model to create the reverse relation.

Imagine you have a model `Team` that has a [ForeignKey][foreign_keys] to another model
`Organisation`.

```python title="models.py" hl_lines="16"
{!> ../docs_src/queries/related_name/example.py !}
```

Because no `related_name` was specified, automatically **Edgy** will call it **`organisations_set`**.


#### Deep into the related_name

Let us create three models:

* Organisation
* Team
* Member

```python title="models.py" hl_lines="16 24-27"
{!> ../docs_src/queries/related_name/models.py !}
```

Above we have the three models declared and inside we declared also three [ForeignKeys][foreign_keys].

* `org` - ForeignKey from Team to Organisation.
* `team` - ForeignKey from Member to Team.
* `second_team` - Another ForeignKey from Member to Team.

Let us also add some data to the models.

```python
{!> ../docs_src/queries/related_name/data.py !}
```

We now can start querying using the `related_name`.

##### Querying using the related_name

* **We want to know all the teams of `acme` organisation**

```python
teams = await acme.teams_set.all()

# [<Team: Team(id=1)>, <Team: Team(id=2)>, <Team: Team(id=3)>]
```

!!! Warning
    Because in the `org` foreign key of the `Team` model no `related_name` was not specified.
    Edgy automatically generated the `teams_set` that is accessible from the `Organisation`.
    Check the [default behaviour](#auto-generating) to understand.

* **We want the team where the members of the blue team belong to**

```python
teams = await acme.teams_set.filter(members=blue_team).get()

# <Team: Team(id=2)>
```

**Nested transversal queries**

Did you see what happened here? Did you notice the `members`? The members is also a reverse query
that links the `Member` model to the `Team`.

This means you can also do nested and transversal queries through your models.

Let us continue with some more examples to understand this better.

* **We want to know which team `charlie` belongs to**

```python
team = await acme.teams_set.filter(members__email=charlie.email).get()

# <Team: Team(id=1)>
```

Again, we use the `members` related name declared in `Member` model that is a
[ForeignKey][foreign_keys] to the `Team` and filter by the `email`.

##### Nested Queries

This is where things get interesting. What happens if you need to go deep down the rabbit hole and
do even more nested queries?

Ok, lets now add two more models to our example.

* User
* Profile

!!! Warning
    These are used only for explanation reasons and not to be perfectly aligned.

We should now have something like this:

```python title="models.py" hl_lines="38-40 47"
{!> ../docs_src/queries/related_name/new_models.py !}
```

We now have another two foreign keys:

* `member` - ForeignKey from User to Member.
* `user` - ForeignKey from Profile to User.

And the corresponding **related names**:

* `users` - The related name for the user foreign key.
* `profiles` - The related name for the profile foreign key.

Let us also add some data into the database.

```python hl_lines="16-17"
{!> ../docs_src/queries/related_name/new_data.py !}
```

This should "deep enough" to understand and now we want to query as deep as we need to.

* **We want to know what team monica belongs to and we want to make sure the user name is also checked**

```python
team = await acme.teams_set.filter(
        members__email=monica.email, members__users__name=user.name
).get()

# <Team: Team(id=4)>
```

This is great, as expected, `monica` belongs to the `green_team` which is the `id=4`.

* **We want to know what team monica belongs by checking the email, user name and the profile type**

```python
team = await acme.teams_set.filter(
    members__email=monica.email,
    members__users__name=user.name,
    members__users__profiles__profile_type=profile.profile_type,
)

# <Team: Team(id=4)>
```

Perfect! We have our results as expected.

This of course in production wouldn't make too much sense to have the models designed in this way
but this shows how deep you can go with the related names reverse queries.

[relationships]: ../relationships.md
[fields]: ../fields.md
[foreign_keys]: ../fields.md#foreignkey
