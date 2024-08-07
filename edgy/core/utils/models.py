from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple, Type

import edgy

if TYPE_CHECKING:
    from pydantic import ConfigDict

    from edgy import Model
    from edgy.core.db.models.metaclasses import MetaInfo

type_ignored_setattr = setattr


def create_edgy_model(
    __name__: str,
    __module__: str,
    __definitions__: Optional[Dict[str, Any]] = None,
    __metadata__: Optional[Type["MetaInfo"]] = None,
    __qualname__: Optional[str] = None,
    __config__: Optional["ConfigDict"] = None,
    __bases__: Optional[Tuple[Type["Model"]]] = None,
    __proxy__: bool = False,
    __pydantic_extra__: Any = None,
) -> Type["Model"]:
    """
    Generates an `edgy.Model` with all the required definitions to generate the pydantic
    like model.
    """

    if not __bases__:
        __bases__ = (edgy.Model,)

    qualname = __qualname__ or __name__
    core_definitions = {
        "__module__": __module__,
        "__qualname__": qualname,
        "__is_proxy_model__": __proxy__,
    }
    if not __definitions__:
        __definitions__ = {}

    core_definitions.update(**__definitions__)

    if __config__:
        core_definitions.update(**{"model_config": __config__})
    if __metadata__:
        core_definitions.update(**{"Meta": __metadata__})
    if __pydantic_extra__:
        core_definitions.update(**{"__pydantic_extra__": __pydantic_extra__})

    model: Type[Model] = type(__name__, __bases__, core_definitions)
    return model


def generify_model_fields(model: Type["Model"]) -> Dict[Any, Any]:
    """
    Makes all fields generic when a partial model is generated or used.
    This also removes any metadata for the field such as validations making
    it a clean slate to be used internally to process dynamic data and removing
    the constraints of the original model fields.
    """
    fields = {}

    # handle the nested non existing results
    for name, field in model.model_fields.items():
        type_ignored_setattr(field, "annotation", Any)
        type_ignored_setattr(field, "null", True)
        type_ignored_setattr(field, "metadata", [])
        fields[name] = field
    return fields
