from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, cast
from warnings import warn

from edgy.core.db.fields.base import BaseForeignKey, RelationshipField

if TYPE_CHECKING:  # pragma: no cover
    from edgy.core.connection.database import Database
    from edgy.core.db.fields.foreign_keys import BaseForeignKeyField
    from edgy.core.db.fields.many_to_many import BaseManyToManyForeignKeyField
    from edgy.core.db.fields.types import BaseFieldType
    from edgy.core.db.models.types import BaseModelType
    from edgy.core.db.relationships.related_field import RelatedField
    from edgy.protocols.relationship_crawl import RelationshipCrawlFn


@dataclass(slots=True, frozen=True, kw_only=True)
class RelationshipCrawlResult:
    """
    A named tuple to encapsulate the results of a relationship crawl operation.

    Attributes:
        model_class (type["BaseModelType"]): The final model class reached
                                             after traversing the relationship path.
        field_name (str): The name of the current field that was in the path.
        operator (str | None): The query operator extracted from the path (e.g., "exact", "icontains").
                               None if no operator is specified.
        forward_path (str): The accumulated path traversed in the "forward" direction
                            (from the initial model to the final model).
        reverse_path (str | Literal[False]): The accumulated path for reversing the
                                             relationship. This can be False if the
                                             path cannot be reversed or is not applicable.
        last_cross_db_remainder (str): Last remaing part of the oath if a cross-database
        cross_db_remainder (str): Full remaining part of the path if a cross-database
                                  relationship was encountered and traversal stopped.
    """

    model_class: type[BaseModelType]
    field_name: str
    operator: str
    forward_path: str
    reverse_path: str | Literal[False]
    last_cross_db_remainder: str
    cross_db_remainder: str

    def __iter__(self) -> Any:
        warn(
            "Unpacking a RelationshipCrawlResult is deprecated. Access the attributes direct.",
            DeprecationWarning,
            stacklevel=2,
        )
        return iter(
            (
                self.model_class,
                self.field_name,
                self.operator,
                self.forward_path,
                self.reverse_path,
                self.cross_db_remainder,
            )
        )

    def __getitem__(self, key: int) -> Any:
        warn(
            "Accessing a RelationshipCrawlResult like a tuple is deprecated. Access the attributes direct.",
            DeprecationWarning,
            stacklevel=2,
        )
        return (
            self.model_class,
            self.field_name,
            self.operator,
            self.forward_path,
            self.reverse_path,
            self.cross_db_remainder,
        )[key]


def crawl_relationship(
    model_class: type[BaseModelType],
    path: str,
    *,
    embed_parent: None | tuple[str, str] = None,
    model_database: Database | None = None,
    callback_fn: None | RelationshipCrawlFn = None,
    traverse_last: bool = False,
    allow_crossing_db: bool = False,
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
    Kwargs:
        embed_parent (tuple[str, str] | None): Provide a embed_parent value from e.g. QuerySet.
        model_database ("Database" | None): The database instance associated with the
                                            current `model_class`. Used for cross-database checks.
                                            Defaults to None.
        callback_fn (None | Callable[..., None]): An optional callback function to be called at each step
                           of the traversal. It receives various parameters about
                           the current state of the crawl. Defaults to None.
                           This can be used to early stop traversals. E.g. to stop loops.
        traverse_last (bool): If True, the last identified field in the path will
                              also be traversed as a relationship. This is useful
                              for scenarios where the final segment is itself
                              a relationship. Defaults to False.
        allow_crossing_db (bool): If True, the databases can be crossed.

    Returns:
        RelationshipCrawlResult: A NamedTuple containing the details of the
                                 crawl result, including the final model class,
                                 field name, operator, forward and reverse paths,
                                 and any cross-database remainder.

    Raises:
        ValueError: If an attempt is made to cross a non-relationship or non-existent field with
                    remaining path segments.
                    If no_operator was provided and an operator was found.
    """
    if embed_parent:
        # If a prefix is defined and the key starts with it, remove the prefix.
        if embed_parent[1] and path.startswith(embed_parent[1]):
            path = path.removeprefix(embed_parent[1]).removeprefix("__")
        elif not path:
            path = embed_parent[0]
        else:
            # Otherwise, prepend the parent alias to the key.
            path = f"{embed_parent[0]}__{path}"
    field: BaseFieldType | None = None
    forward_prefix_path = ""
    reverse_path: str | Literal[False] = ""
    operator: str = ""
    field_name: str = path
    cross_db_remainder: str = ""
    last_cross_db_remainder: str = ""

    # Loop while there are still segments in the path to process.
    while path:
        # Split the path into the current field name and the remaining path.
        splitted = path.split("__", 1)
        field_name = splitted[0]
        # Get the field from the current model_class's meta fields.
        field = model_class.meta.fields.get(field_name)
        in_columns_or_fields = field is not None or field_name in model_class.table.columns

        # Check if the field is a RelationshipField and there are more segments.
        if isinstance(field, RelationshipField) and len(splitted) == 2:
            # Traverse the relationship field to get the new model class and reverse parts.
            model_class_new, reverse_part, path = field.traverse_field(path)

            # Check for cross-database relationships.
            if field.is_cross_db(model_database):
                # If it's a cross-DB relationship record the remainder.
                if not cross_db_remainder:
                    cross_db_remainder = path
                last_cross_db_remainder = path
                # Stop the travel if not allowed
                if not allow_crossing_db:
                    break
            # If passed, update the model_class and reset model_database.
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
                    field_name=field_name,
                    reverse_path=reverse_path,
                    forward_path=forward_prefix_path,
                    reverse=reverse,
                    # here None
                    operator=None,  # Operator is not relevant at this stage of traversal.
                    cross_db_remainder=cross_db_remainder,
                    last_cross_db_remainder=last_cross_db_remainder,
                )

            # Update the forward_prefix_path.
            if forward_prefix_path:
                forward_prefix_path = f"{forward_prefix_path}__{field_name}"
            else:
                forward_prefix_path = field_name
        # If there are two parts but the first part is not a relationship field.
        elif len(splitted) == 2:
            # If the second part does not contain "__", it's likely an operator.
            # Operators are not allowed to contain __
            # if a forward path was provided, the field_name must either exist in columns or in fields
            if "__" not in splitted[1] and (not forward_prefix_path or in_columns_or_fields):
                if splitted[1] == "":
                    raise ValueError("Path unsanitized, ends with `__`.")
                operator = splitted[1]
                break
            else:
                if field is None:
                    raise ValueError(
                        f"Tried to cross field: `{field_name}` which does not exist "
                        f"remainder: `{splitted[1]}`."
                    )
                # Raise an error if trying to cross a non-relationship field with further segments.
                raise ValueError(
                    f"Tried to cross field: `{field_name}` of type `{field!r}`, "
                    f"remainder: `{splitted[1]}`."
                )
        else:
            # If only one part remains, it's the final field name, and the operator is empty
            operator = ""
            break

    # Check for cross-database relationships of the last field.
    if isinstance(field, RelationshipField) and field.is_cross_db(model_database):
        # If it's a cross-DB relationship record the remainder.
        if not cross_db_remainder:
            cross_db_remainder = path
        last_cross_db_remainder = path

    # Handle the last segment if traverse_last is True and the last field was a RelationshipField and
    # we can cross the db.
    if (
        traverse_last
        and isinstance(field, RelationshipField)
        and (not cross_db_remainder or allow_crossing_db)
    ):
        model_class, reverse_part, path = field.traverse_field(path)
        # either field name alone if prefix path is empty or concatenated
        forward_prefix_path = (
            f"{forward_prefix_path}__{field_name}" if forward_prefix_path else field_name
        )
        field_name = ""
        # Travelling reverse a foreign key
        reverse = not isinstance(field, BaseForeignKey)
    else:
        # If not traversing the last field, set reverse_part to field_name.
        reverse_part = field_name
        # Not travelling reverse a foreign key
        reverse = False
    # Final update to reverse_path.
    if reverse_part and reverse_path is not False:
        reverse_path = f"{reverse_part}__{reverse_path}" if reverse_path else reverse_part
    else:
        reverse_path = False

    # Call the callback function one last time with the final state if a field was found.
    if callback_fn:
        callback_fn(
            model_class=model_class,
            # can be None
            field=field,
            field_name=field_name,
            reverse_path=reverse_path,
            forward_path=forward_prefix_path,
            reverse=reverse,
            # here always string. In case of no operator empty ""
            operator=operator,
            cross_db_remainder=cross_db_remainder,
            last_cross_db_remainder=last_cross_db_remainder,
        )

    # Return the comprehensive result of the relationship crawl.
    return RelationshipCrawlResult(
        model_class=model_class,
        field_name=field_name,
        operator=operator,
        forward_path=forward_prefix_path,
        reverse_path=reverse_path,
        cross_db_remainder=cross_db_remainder,
        last_cross_db_remainder=last_cross_db_remainder,
    )


def get_related_column_keys(field: BaseFieldType) -> Collection[str]:
    """Return for a relation field the related columns. M2M relations are expanded."""
    # You can think it as a form of traversal, just to return the column key names
    owner_meta = field.owner.meta
    # try to pollute less the utils namespace, so check the information via meta
    if field.name in owner_meta.foreign_key_fields:
        # easiest case: is a BaseForeignKeyField in forward direction and we can use related_columns
        return cast("BaseForeignKeyField", field).related_columns.keys()
    elif field.name in owner_meta.many_to_many_fields:
        m2m_field = cast("BaseManyToManyForeignKeyField", field)
        # if ManytoMany in forward direction: get the internal through foreign key and return
        # the column keys of the foreign key pointing reverse to the start.
        return cast("type[BaseModelType]", m2m_field.through).meta.field_to_column_names[
            m2m_field.from_foreign_key
        ]
    else:
        # RelatedField, reverse direction. Find the foreign key the related field is the reverse
        # and return the column keys of the foreign key
        assert type(field).__name__ == "RelatedField", f"Unhandled relation field: {field!r}"
        field = cast("RelatedField", field).foreign_key
        return field.owner.meta.field_to_column_names[field.name]
