# Contenttypes

## Intro

Relational database systems operate using tables that are generally independent, except for foreign keys, which work well in most cases. However, this design has a minor drawback.

Querying and iterating generically across tables and domains can be challenging. This is where ContentTypes come into play. ContentTypes abstract all tables into a single table, providing a powerful solution. By maintaining a single table with backlinks to all other tables, it becomes possible to create generic tables with logic that applies universally.

Typically, uniqueness can only be enforced within individual tables. However, with the ContentType table, it is now possible to enforce uniqueness across multiple tables—this can be achieved efficiently by compressing the data, for example, using a hash.

```python
{!> ../docs_src/contenttypes/basic.py !}
```

!!! Implementation Note
    Since we allow various types of primary keys, we must inject a unique field into every model to enable backward traversal.

### Example: The art of comparing apples with pears

Imagine we need to compare apples and pears based on weight, ensuring only fruits with different weights are considered.

Since weight is a small number, we can simply store it in the `collision_key` field of ContentType.

```python
{!> ../docs_src/contenttypes/collision.py !}
```

If we know that the comparison across all domains is based solely on weight, we can even replace the `collision_key` field with an `IntegerField`.

```python
{!> ../docs_src/contenttypes/customized_collision.py !}
```

Or, if we now allow fruits with the same weight, we can simply remove the uniqueness constraint from the `collision_key` field.

```python
{!> ../docs_src/contenttypes/customized_nocollision.py !}
```

### Example 2: Snapshotting

Sometimes, you may need to track when an object is created or updated to narrow the search scope or mark outdated data for deletion.

Edgy makes this process straightforward:

```python
{!> ../docs_src/contenttypes/snapshotting.py !}
```

## Tricks

### CASCADE Deletion Issues or Constraint Problems

Sometimes, CASCADE deletion is not possible due to limitations in the underlying database technology (see the snapshotting example) or unexpected constraint behavior, such as performance slowdowns.

To handle this, you can switch to virtual CASCADE deletion without enforcing a constraint by setting `no_constraint = True`.

If you need a completely different deletion strategy for a specific model, you can use the `ContentTypeField` and override all extras.

### Using in Libraries

If activated, `ContentType` is always available under the name `ContentType` and as a `content_type` attribute on the registry.

If the `content_type` attribute on the registry is not `None`, you can be sure that `ContentType` is available.

### Opting Out

Some models should not be referencable by `ContentType`.

To opt out, override `content_type` on the model with any field. Use `ExcludeField` to remove the field entirely.

### Tenancy Compatibility

`ContentType` is tenancy-compatible out of the box.
