from typing import TYPE_CHECKING, Any, Dict, Iterable, Set, Union, cast

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


def pk_to_dict(model: "EdgyBaseModel", pk: Any, is_partial: bool = False) -> Dict[str, Any]:
    try:
        if len(model.pknames) == 1:
            if isinstance(pk, dict):
                pk = pk[model.pknames[0]]
            elif hasattr(pk, model.pknames[0]):
                pk = getattr(pk, model.pknames[0])
            return {model.pknames[0]: pk}
    except (KeyError, AttributeError) as exc:
        if is_partial:
            return {}
        raise exc
    retdict = {}
    if isinstance(pk, dict):
        for pkname in model.pknames:
            try:
                retdict[pkname] = pk[pkname]
            except KeyError as exc:
                if not is_partial:
                    raise exc
    else:
        for pkname in model.pknames:
            try:
                retdict[pkname] = getattr(pk, pkname)
            except AttributeError as exc:
                if not is_partial:
                    raise exc
    return retdict


def pk_from_model(model: "EdgyBaseModel", always_dict: bool = False) -> Union[Dict[str, Any], Any]:
    if not always_dict and len(model.pknames) == 1:
        return getattr(model, model.pknames[0], None)
    else:
        d = {}
        has_non_null = False
        for pkname in model.pknames:
            d[pkname] = getattr(model, pkname, None)
            if d[pkname] is not None:
                has_non_null = True
        if always_dict or has_non_null:
            return d
        else:
            return None


def pk_from_model_to_clauses(model: "EdgyBaseModel") -> Iterable[Any]:
    for pkcolumn in model.pkcolumns:
        yield getattr(model.table.columns, pkcolumn) == getattr(model, pkcolumn)
