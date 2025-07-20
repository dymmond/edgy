from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, NamedTuple

from edgy.core.db.fields.base import BaseForeignKey, RelationshipField

if TYPE_CHECKING:  # pragma: no cover
    from edgy.core.connection.database import Database
    from edgy.core.db.models.types import BaseModelType


class RelationshipCrawlResult(NamedTuple):
    """
    A named tuple to encapsulate the results of a relationship crawl operation.

    Attributes:
        model_class (type["BaseModelType"]): The final model class reached
                                             after traversing the relationship path.
        field_name (str): The name of the field that was last resolved in the path.
        operator (str | None): The query operator extracted from the path (e.g., "exact", "icontains").
                               None if no operator is specified.
        forward_path (str): The accumulated path traversed in the "forward" direction
                            (from the initial model to the final model).
        reverse_path (str | Literal[False]): The accumulated path for reversing the
                                             relationship. This can be False if the
                                             path cannot be reversed or is not applicable.
        cross_db_remainder (str): Any remaining part of the path if a cross-database
                                  relationship was encountered and traversal stopped.
    """

    model_class: type[BaseModelType]
    field_name: str
    operator: str | None
    forward_path: str
    reverse_path: str | Literal[False]
    cross_db_remainder: str


def crawl_relationship(
    model_class: type[BaseModelType],
    path: str,
    *,
    model_database: Database | None = None,
    callback_fn: Any = None,
    traverse_last: bool = False,
) -> RelationshipCrawlResult:
    """
    Crawls a relationship path, typically used for query lookups that span
    across related models (e.g., "author__book__title"). It resolves each
    segment of the path, updating the current model class and tracking both
    forward and reverse traversal paths. It can also identify query operators
    and handle cross-database relationships.

    Args:
        model_class (type["BaseModelType"]): The starting model class for the crawl.
        path (str): The relationship path to traverse, typically in a "field__field__operator"
                    format.
        model_database ("Database" | None): The database instance associated with the
                                            current `model_class`. Used for cross-database checks.
                                            Defaults to None.
        callback_fn (Any): An optional callback function to be called at each step
                           of the traversal. It receives various parameters about
                           the current state of the crawl. Defaults to None.
        traverse_last (bool): If True, the last identified field in the path will
                              also be traversed as a relationship. This is useful
                              for scenarios where the final segment is itself
                              a relationship. Defaults to False.

    Returns:
        RelationshipCrawlResult: A NamedTuple containing the details of the
                                 crawl result, including the final model class,
                                 field name, operator, forward and reverse paths,
                                 and any cross-database remainder.

    Raises:
        ValueError: If an attempt is made to cross a non-relationship field with
                    remaining path segments.
    """
    field = None
    forward_prefix_path = ""
    reverse_path: str | Literal[False] = ""
    operator: str | None = "exact"
    field_name: str = path
    cross_db_remainder: str = ""

    # Loop while there are still segments in the path to process.
    while path:
        # Split the path into the current field name and the remaining path.
        splitted = path.split("__", 1)
        field_name = splitted[0]
        # Get the field from the current model_class's meta fields.
        field = model_class.meta.fields.get(field_name)

        # Check if the field is a RelationshipField and there are more segments.
        if isinstance(field, RelationshipField) and len(splitted) == 2:
            # Traverse the relationship field to get the new model class and reverse parts.
            model_class_new, reverse_part, path = field.traverse_field(path)

            # Check for cross-database relationships.
            if field.is_cross_db(model_database):
                # If it's a cross-DB relationship, stop traversal and record the remainder.
                cross_db_remainder = path
                break
            else:
                # If not cross-DB, update the model_class and reset model_database.
                model_class = model_class_new
                model_database = None  # Reset database context for the new model.

            # Determine if the relationship is a reverse relationship (not a BaseForeignKey).
            reverse = not isinstance(field, BaseForeignKey)

            # Update the reverse_path if applicable.
            if reverse_part and reverse_path is not False:
                reverse_path = f"{reverse_part}__{reverse_path}" if reverse_path else reverse_part
            else:
                reverse_path = False

            # Call the callback function if provided.
            if callback_fn:
                callback_fn(
                    model_class=model_class,
                    field=field,
                    reverse_path=reverse_path,
                    forward_path=forward_prefix_path,
                    reverse=reverse,
                    operator=None,  # Operator is not relevant at this stage of traversal.
                    cross_db_remainder=cross_db_remainder,
                )

            # Update the forward_prefix_path.
            if forward_prefix_path:
                forward_prefix_path = f"{forward_prefix_path}__{field_name}"
            else:
                forward_prefix_path = field_name
        # If there are two parts but the first part is not a relationship field.
        elif len(splitted) == 2:
            # If the second part does not contain "__", it's likely an operator.
            if "__" not in splitted[1]:
                operator = splitted[1]
                break
            else:
                # Raise an error if trying to cross a non-relationship field with further segments.
                raise ValueError(
                    f"Tried to cross field: {field_name} of type {field!r}, "
                    f"remainder: {splitted[1]}"
                )
        else:
            # If only one part remains, it's the final field name, and the operator is "exact".
            operator = "exact"
            break

    # Handle the last segment if traverse_last is True and the last field was a RelationshipField.
    if traverse_last and isinstance(field, RelationshipField):
        model_class, reverse_part, path = field.traverse_field(path)
        reverse = not isinstance(field, BaseForeignKey)
    else:
        # If not traversing the last field, set reverse to False and reverse_part to field_name.
        reverse = False
        reverse_part = field_name

    # Final update to reverse_path.
    if reverse_part and reverse_path is not False:
        reverse_path = f"{reverse_part}__{reverse_path}" if reverse_path else reverse_part
    else:
        reverse_path = False

    # Call the callback function one last time with the final state if a field was found.
    if callback_fn and field is not None:
        callback_fn(
            model_class=model_class,
            field=field,
            reverse_path=reverse_path,
            forward_path=forward_prefix_path,
            reverse=reverse,
            operator=operator,
            cross_db_remainder=cross_db_remainder,
        )

    # Return the comprehensive result of the relationship crawl.
    return RelationshipCrawlResult(
        model_class=model_class,
        field_name=field_name,
        operator=operator,
        forward_path=forward_prefix_path,
        reverse_path=reverse_path,
        cross_db_remainder=cross_db_remainder,
    )
