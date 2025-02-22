# Annotating Queries

Annotating queries in Edgy presents some unique challenges due to the use of hash functions with prefix (select_related) paths for generating stable join names. However, if you primarily use subqueries, these issues are less likely to arise.

## Annotating a Child with Parent Columns

When working with nested relationships, you might need to access parent columns from a child element. The `reference_select` function addresses this, functioning similarly to Django's `F()` function but with broader applicability.

=== "Model"

    ```python
    {!> ../docs_src/queries/annotate/child_annotate.py !}
    ```

    **Explanation:**

    -   The `reference_select` function allows you to include columns from related tables (parents) in your query results.
    -   In this example, it's used to bring parent columns into the child's result set, making parent data accessible alongside child data.

=== "StrictModel"

    ```python
    {!> ../docs_src/queries/annotate/strict_child_annotate.py !}
    ```

    **Explanation:**

    -   When using `StrictModel`, every attribute in the query result must correspond to a defined field.
    -   `PlaceHolderField(null=True)` is used to reserve attribute names for assignment, ensuring that the query results can be correctly mapped to the model's fields.
    -   This is crucial for maintaining type safety and preventing unexpected errors when working with strictly defined models.

!!! Warning
    With `StrictModel`, ensure that all query result names match defined fields. Use `PlaceHolderField(null=True)` to reserve attribute names for assignment.

## Annotating and `embed_parent`

`reference_select` executes before embedding, enabling the addition of parent attributes to grandchild elements.

```python
{!> ../docs_src/queries/annotate/child_annotate_embed.py !}
```

**Explanation:**

-   The `embed_parent` feature allows you to include parent data when fetching related children.
-   By using `reference_select` before embedding, you can augment the data available to the grandchild with additional attributes from the parent.
-   This is particularly useful for deeply nested relationships where you need to access data from multiple levels.

## Annotating Child Attributes to the Parent

`reference_select` operates from the perspective of the main query, allowing child attributes to be set via `reference_select({"user": {"user_name", "user__name"}})` on the child.

Alternatively, you can manually use the `hash_tablekey` helper function (though this is not recommended).

```python
{!> ../docs_src/queries/annotate/parent_annotate.py !}
```

**Explanation:**

-   `reference_select` allows you to pull data not only from parent tables to children, but also from children to parents.
-   The dictionary passed to `reference_select` specifies the relationship and the fields to be included.
-   In this example, child attributes (e.g., `user_name`, `user__name`) are being added to the parent's result set.
-   Using `hash_tablekey` manually is possible but generally discouraged due to its complexity and potential for errors.

## Annotating and Subqueries

Beyond referencing child-parent structures, you can reference arbitrary select statements using `extra_select`.

```python
{!> ../docs_src/queries/annotate/subquery_annotate.py !}
```

**Explanation:**

-   `extra_select` allows you to include custom SQL expressions or subqueries in your query results.
-   You can add multiple `extra_select` entries, each with a unique label to prevent collisions.
-   This provides flexibility to include calculated values or data from other tables that are not directly related through model relationships.
-   The example shows how to add a subquery that counts the number of posts associated with each user.

Furthermore, you can reference Common Table Expressions (CTEs) by knowing their name or providing the column.

**Explanation:**

-   CTEs, like subqueries, can be used to add complex data to your queries.
-   By referencing a CTE's name or providing the necessary column information, you can include the results of the CTE in your query.
-   This allows for more advanced data manipulation and aggregation within your queries.
-   This is very useful for optimizing complex queries by breaking them down into simpler, reusable parts.
