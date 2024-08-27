from typing import TYPE_CHECKING, Any, Iterable, Optional, Set, Type, cast

if TYPE_CHECKING:
    from sqlalchemy import Table

    from edgy.core.connection.database import Database
    from edgy.core.connection.registry import Registry
    from edgy.core.db.models.base import BaseModelType
    from edgy.core.db.models.model import Model


def get_model(registry: "Registry", model_name: str) -> "Model":
    """
    Return the model with capitalize model_name.

    Raise lookup error if no model is found.
    """
    try:
        return cast("Model", registry.models[model_name])
    except KeyError:
        raise LookupError(f"Registry doesn't have a {model_name} model.") from None


def build_pknames(model_class: Any) -> None:
    """
    Set explicit pknames (field names with primary_key=True set)
    """
    meta = model_class.meta
    pknames: Set[str] = set()
    for field_name, field in meta.fields.items():
        if field.primary_key:
            pknames.add(field_name)
    model_class._pknames = tuple(sorted(pknames))


def build_pkcolumns(model_class: Any) -> None:
    """
    Set pkcolumns (columns with primary_key set)
    """
    table = model_class.table
    pkcolumns: Set[str] = set()
    for column in table.columns:
        if column.primary_key:
            # key is the sqlalchemy name, in our case name and key should be identically
            pkcolumns.add(column.key)
    model_class._pkcolumns = tuple(sorted(pkcolumns))


def from_model_to_clauses(model: "BaseModelType") -> Iterable[Any]:
    for column in model.columns_for_load:
        yield getattr(model.table.columns, column) == getattr(model, column)


def apply_instance_extras(
    model: "BaseModelType",
    model_class: Type["BaseModelType"],
    schema: Optional[str] = None,
    database: Optional["Database"] = None,
    table: Optional["Table"] = None,
) -> "Model":
    model.__using_schema__ = schema
    if table is None:
        # Apply the schema to the model instance
        model.table = model_class.table_schema(schema)
    else:
        model.table = table
    if database is not None:
        # Set the database to the model instance
        model.database = database
    return model
