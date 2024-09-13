# Contenttypes

## Intro

Relational database systems work with the concept of tables. Tables are independent of each other except
for foreign keys which works nice in most cases but this design has a little drawback.

Querying, iterating generically across tables and domains is hard, this is where ContentTypes come in play.
ContentTypes abstract all the tables in one table, which is quite powerful. By having
only one table with back links to all the other tables, it is possible to have generic tables which logic applies
to all other tables.
Normally you can only enforce uniqueness per table, now it this possible via the ContentType table for data
in different tables (you just have to compress them usefully e.g. by a hash).

```python
{!> ../docs_src/contenttypes/basic.py !}
```

!!! Implementation Note
    Because we allow all sorts of primary keys we have to inject an unique field in every model to traverse back.

### Example: The art of comparing apples with pears

Let's imagine we have to compare apples with pears via weight. We want only fruits with different weights.
Because weight is a small number we just can put it in the
collision_key field of ContentType.

```python
{!> ../docs_src/contenttypes/collision.py !}
```

If we know we compare over all domains just weight, we can
even replace the collision_key field via an IntegerField.

```python
{!> ../docs_src/contenttypes/customized_collision.py !}
```

Or now we allow fruits with the same weight. Let's just remove the uniqueness from the collision_key field.


```python
{!> ../docs_src/contenttypes/customized_nocollision.py !}
```

### Example 2: Snapshotting

Sometime you want to know when an object is created (or updated), so you can reduce the search area
or mark old data for deletion.

Edgy is able to do this quite easily:


```python
{!> ../docs_src/contenttypes/snapshotting.py !}
```

If you don't want deletions caused by ContentTypes or doesn't like some many constraints you can use:

```python
{!> ../docs_src/contenttypes/snapshotting_no_constraints.py !}
```

## Tricks

### Using in libraries

ContentType is always available under the name `ContentType` if activated and as a `content_type` attribute on registry.

If the attribute `content_type` on registry is not None, you can be assured ContentType is available.


### Opting out

Some models may should not be referencable by ContentType.

You can opt out by overwriting `content_type` on the model to opt out with any Field.
Use `ExcludeField` to remove the field entirely.

### Tenancy compatibility

ContentType is out of the box tenancy compatible. You may want to use `no_constraints` in case of many, dynamic tenants.
