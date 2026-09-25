# Many-to-One Relations

Many-to-one relations are the inverse of a `ForeignKey`. There is only an implicit field for this, which is added to the target model with the related name specified or automatically generated. The interface is quite similar to [ManyToMany](./many-to-many.md).

## Operations

With the many-to-one relation, you can perform all the normal operations of searching from normal queries to the [related_name][related_name] as per normal search.

Many-to-one relations allow three different methods when using them (the same applies for the reverse side).

* `add(obj) -> finalobj | None` - Adds a record to the relation (Updates the ForeignKey). Return `None` when adding was not possible.
* `create(*args, **kwargs) -> finalobj | None` - Create a new record and add it to the relation. This method is deviating from `QuerySet.create` by returning `None` when not succeeding.
* `remove(obj) -> None` - Removes a record from the relation (sets the ForeignKey to None).
* `add_many(*objs) -> list[finalobj | None]` - Adds multiple records to the ManyToMany. Return list with return values of `add`.
* `remove_many(*objs) -> None` - Removes multiple records from the relation.

And we have normal QuerySet operations.

Let us see how it looks by using the following example.

```python
{!> ../docs_src/queries/manytoone/example.py !}
```

#### add()

You can now add members to teams, something like this.

```python
member = await TeamMember.query.create(name="member1")
blue_team = await Team.query.create(name="Blue Team")

await blue_team.members.add(member)
```

#### create()

You can fuse this to:

```python
blue_team = await Team.query.create(name="Blue Team")
green_team = await Team.query.create(name="Green Team")
member1 = await blue_team.members.create(name="edgy")
member2 = await green_team.members.create(name="fastapi")
```

This is also more performant because less transactions are required.

#### remove()

You can now remove members from teams, something like this.

```python
blue_team = await Team.query.create(name="Blue Team")

member = await blue_team.members.create(name="member1")
# and now remove
await blue_team.members.remove(member)
```

Hint: when unique, remove works also without argument.

#### Related name

When a [related_name][related_name] is not defined, Edgy will automatically generate one with the following format:

```shell
<foreignkey>s_set
```

[related_name]: ./related-name.md
