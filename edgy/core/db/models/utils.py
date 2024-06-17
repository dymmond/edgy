from typing import TYPE_CHECKING, Any, Iterable, Set, cast

from edgy.core.connection.registry import Registry

if TYPE_CHECKING:
    from edgy.core.db.models.base import EdgyBaseModel
    from edgy.core.db.models.model import Model


def get_model(registry: Registry, model_name: str) -> "Model":
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
    Set explicit pknames

    Raise error if primary key column has no field associated.
    """
    meta = model_class.meta
    pknames: Set[str] = set()
    for field_name, field in meta.fields_mapping.items():
        if field.primary_key:
            pknames.add(field_name)
    model_class._pknames = tuple(sorted(pknames))


def build_pkcolumns(model_class: Any) -> None:
    """
    Set pkcolumns

    Raise error if primary key column has no field associated.
    """
    table = model_class.table
    pkcolumns: Set[str] = set()
    for column in table.columns:
        if column.primary_key:
            # key is the sqlalchemy name, in our case name and key should be identically
            pkcolumns.add(column.key)
    model_class._pkcolumns = tuple(sorted(pkcolumns))


def from_model_to_clauses(model: "EdgyBaseModel") -> Iterable[Any]:
    for column in model.columns_for_load:
        yield getattr(model.table.columns, column) == getattr(model, column)
