# Annotating queries

Annotating queries is a bit difficult in edgy because we use a hash function with a prefix (select_related) path to
generate stable names for joins.
But given you mostly use just a subquery you won't run often in this case.

## Annotating a child with the parent columns

We have embed target for drilling down to a child element but sometimes lack parameters of the parent.
Here comes the function `reference_select` to help. This works analogue to django's `F()` function but is more generic.


=== "Model"

    ```python
    {!> ../docs_src/queries/annotate/child_annotate.py !}
    ```

=== "StrictModel"

    ```python
    {!> ../docs_src/queries/annotate/strict_child_annotate.py !}
    ```

!!! Warning
    In case you use the `StrictModel` every name where the query result is attached **must** be a field.
    You can use PlaceHolderField(null=True) for reserving an attribute name for assignment.

## Annotating and embed_parent

`reference_select` is executed before embedding. This can be helpful to add some parent attributes to the grand child.

```python
{!> ../docs_src/queries/annotate/child_annotate_embed.py !}
```

## Annotating child attributes to the parent

`reference_select` point of view is always the main query. This means you can set child attributes via

`reference_select({"user": {"user_name", "user__name"}})` to the child itself.

Or you can do all manually by using the helper function `hash_tablekey` (not recommended).

```python
{!> ../docs_src/queries/annotate/parent_annotate.py !}
```

## Annotating and subqueries

Until now we referenced only child parent structures but we can also reference arbitary select statements.
How to insert some? Using `extra_select`.
You can add as many as you want and label them as you want but are responsible for collisions.

```python
{!> ../docs_src/queries/annotate/subquery_annotate.py !}
```

The cool thing is you are not limited to subqueries. CTEs can be referenced too, you just need to know the name or to provide the column.
