from typing import TYPE_CHECKING, Any, Literal, NamedTuple, Optional, Union

from edgy.core.db.fields.base import BaseForeignKey, RelationshipField

if TYPE_CHECKING:  # pragma: no cover
    from edgy.core.connection.database import Database
    from edgy.core.db.models.types import BaseModelType


class RelationshipCrawlResult(NamedTuple):
    model_class: type["BaseModelType"]
    field_name: str
    operator: Optional[str]
    forward_path: str
    reverse_path: Union[str, Literal[False]]
    cross_db_remainder: str


def crawl_relationship(
    model_class: type["BaseModelType"],
    path: str,
    *,
    model_database: Optional["Database"] = None,
    callback_fn: Any = None,
    traverse_last: bool = False,
) -> RelationshipCrawlResult:
    field = None
    forward_prefix_path = ""
    reverse_path: Union[str, Literal[False]] = ""
    operator: Optional[str] = "exact"
    field_name: str = path
    cross_db_remainder: str = ""
    while path:
        splitted = path.split("__", 1)
        field_name = splitted[0]
        field = model_class.meta.fields.get(field_name)
        if isinstance(field, RelationshipField) and len(splitted) == 2:
            model_class_new, reverse_part, path = field.traverse_field(path)
            if field.is_cross_db(model_database):
                cross_db_remainder = path
                break
            else:
                model_class = model_class_new
                model_database = None
            reverse = not isinstance(field, BaseForeignKey)
            if reverse_part and reverse_path is not False:
                reverse_path = f"{reverse_part}__{reverse_path}" if reverse_path else reverse_part
            else:
                reverse_path = False

            if callback_fn:
                callback_fn(
                    model_class=model_class,
                    field=field,
                    reverse_path=reverse_path,
                    forward_path=forward_prefix_path,
                    reverse=reverse,
                    operator=None,
                    cross_db_remainder=cross_db_remainder,
                )
            if forward_prefix_path:
                forward_prefix_path = f"{forward_prefix_path}__{field_name}"
            else:
                forward_prefix_path = field_name
        elif len(splitted) == 2:
            if "__" not in splitted[1]:
                operator = splitted[1]
                break
            else:
                raise ValueError(
                    f"Tried to cross field: {field_name} of type {field!r}, remainder: {splitted[1]}"
                )
        else:
            operator = "exact"
            break

    if traverse_last and isinstance(field, RelationshipField):
        model_class, reverse_part, path = field.traverse_field(path)
        reverse = not isinstance(field, BaseForeignKey)
    else:
        reverse = False
        reverse_part = field_name
    if reverse_part and reverse_path is not False:
        reverse_path = f"{reverse_part}__{reverse_path}" if reverse_path else reverse_part
    else:
        reverse_path = False
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
    return RelationshipCrawlResult(
        model_class=model_class,
        field_name=field_name,
        operator=operator,
        forward_path=forward_prefix_path,
        reverse_path=reverse_path,
        cross_db_remainder=cross_db_remainder,
    )
