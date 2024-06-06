from typing import TYPE_CHECKING, Any, Dict, Iterable, Union, cast

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
    for k, v in pk_from_model(model, always_dict=True).items():
        yield getattr(model.table.columns, k) == v
