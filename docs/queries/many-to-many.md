# ManyToMany

In a lot of projects out there you see cases where a ManyToMany would be helpful. Django for example,
has that defined as internal model when a field is declared.

In theory, when designing a database, the `ManyToMany` does not exist and it is not possible in
a relational system.

What happens internally is the creation of an intermediary table that links the many to many tables.

## How does it work

As mentioned before, a many to many it is not possible in a relational database, instead, an
intermediary table needs to be created and connect the tables for the said many to many.

This is exactly what edgy does with the [ManyToMany][many_to_many] automatically.

### Quick note

The `ManyToMany` or `ManyToMany` accepts both [Model](../models.md) and string as
a parameter for the `to`.

**Example**

```python
# Using the model directly
class Profile(edgy.Model):
    users: List[User] = edgy.ManyToMany(User)

# Using a string
class Profile(edgy.Model):
    users: List[User] = edgy.ManyToMany("User")
```

### Queries

Queries from a Many2Many field use the `through` model as base when embed_through is empty. This also applies for the reverse related field.
If embed_through is False the virtual base changes to the `target` model.
The same applies if embed_through is not-empty. In this case it is possible to target the embedded model via the embed_through path part.
It is like a virtual path part which can be traversed via the `__` path building.

### Operations

With the many to many you can perform all the normal operations of searching from normal queries
to the [related name][related_name] as per normal search.

ManyToMany allows some different methods when using it (the same applies for the reverse side).

* `add(obj) -> finalobj | None` - Adds a record to the ManyToMany. Return `None` when adding failed, the finalized object with primary key set otherwise.
* `create(*args. **kwargs) -> finalobj | None` - Create a new record and add it to the ManyToMany. Return values like `add`.
* `remove(obj) -> None` - Removes a record to the ManyToMany.
* `add_many(*objs) -> list[finalobj | None]` - Adds multiple records to the ManyToMany. Return list with return values of `add`.
* `remove_many(*objs) -> None` - Removes multiple records to the ManyToMany.

Let us see how it looks by using the following example.

```python hl_lines="17"
{!> ../docs_src/queries/manytomany/example.py !}
```

#### add()

You can now add teams to organisations, something like this.

```python hl_lines="6-7"
blue_team = await Team.query.create(name="Blue Team")
green_team = await Team.query.create(name="Green Team")
organisation = await Organisation.query.create(ident="Acme Ltd")

# Add teams to the organisation
await organisation.teams.add(blue_team)
result = await organisation.teams.add(green_team)
# result is either None or a proxymodel of green_team
```

Why do we need the proxy model when having green_team?
Well yes, you can find the embedded through model here (if enabled) as well as
checking that adding was successful (and there was not already a relationship).

### add_many()

You can now add multiple teams to organisations, something like this.

```python hl_lines="6-7"
blue_team = await Team.query.create(name="Blue Team")
green_team = await Team.query.create(name="Green Team")
red_team = await Team.query.create(name="Red Team")
organisation = await Organisation.query.create(ident="Acme Ltd")

# Add teams to the organisation
results = await organisation.teams.add_many(blue_team, green_team, red_team)
# results contain the proxy models as well as None when the object was added already
```

### remove_many()

You can now remove multiple teams from organisations, something like this.

```python hl_lines="12-13"
blue_team = await Team.query.create(name="Blue Team")
green_team = await Team.query.create(name="Green Team")
red_team = await Team.query.create(name="Red Team")
organisation = await Organisation.query.create(ident="Acme Ltd")

# Add teams to organisation
await organisation.teams.add(blue_team)
await organisation.teams.add(green_team)
await organisation.teams.add(red_team)

# Remove the teams from the organisation
await organisation.teams.remove_many(red_team, blue_team)
```

#### create()

You can fuse this to:


```python hl_lines="4-5"
organisation = await Organisation.query.create(ident="Acme Ltd")

# Add teams to the organisation
await organisation.teams.create(name="Blue Team")
await organisation.teams.create(name="Green Team")
```

#### remove()

You can now remove teams from organisations, something like this.

```python hl_lines="12-13"
blue_team = await Team.query.create(name="Blue Team")
green_team = await Team.query.create(name="Green Team")
red_team = await Team.query.create(name="Red Team")
organisation = await Organisation.query.create(ident="Acme Ltd")

# Add teams to organisation
await organisation.teams.add(blue_team)
await organisation.teams.add(green_team)
await organisation.teams.add(red_team)

# Remove the teams from the organisation
await organisation.teams.remove(red_team)
await organisation.teams.remove(blue_team)
# green team is removed because it is unique
await organisation.teams.remove()
```

Hint: when only a relation is left, remove works also without argument.

#### Related name

The same way you define [related names][related_name] for foreign keys, you can do the same for
the [ManyToMany][many_to_many].

When a `related_name` is not defined, Edgy will automatically generate one with the following
format:

```shell
<table-to-many2many>_<through-model-name>s_set
```

##### Example without related name

```python hl_lines="17"
{!> ../docs_src/queries/manytomany/no_rel.py !}
```

```python hl_lines="11"
{!> ../docs_src/queries/manytomany/no_rel_query_example.py !}
```

As you can see, because no `related_name` was provided, it defaulted to `team_organisationteams_set`.

##### Example with related name

```python hl_lines="17"
{!> ../docs_src/queries/manytomany/example.py !}
```

!!! Tip
    The way you can query using the [related name][related_name] are described in detail in the
    [related name][related_name] section and has the same level of functionality as per normal
    foreign key.

You can now query normally, something like this.

```python hl_lines="11"
{!> ../docs_src/queries/manytomany/query_example.py !}
```

[many_to_many]: ../fields/index.md#manytomany
[related_name]: ./related-name.md
