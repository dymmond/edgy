import contextlib
from typing import TYPE_CHECKING, Any, Optional

from pydantic_core import PydanticUndefined

if TYPE_CHECKING:
    from pydantic import ConfigDict

    from edgy.core.db.models import Model
    from edgy.core.db.models.metaclasses import MetaInfo
    from edgy.core.db.models.types import BaseModelType


def create_edgy_model(
    __name__: str,
    __module__: str,
    __definitions__: Optional[dict[str, Any]] = None,
    __metadata__: Optional["MetaInfo"] = None,
    __qualname__: Optional[str] = None,
    __config__: Optional["ConfigDict"] = None,
    __bases__: Optional[tuple[type["BaseModelType"], ...]] = None,
    __proxy__: bool = False,
    __pydantic_extra__: Any = None,
    __type_kwargs__: Optional[dict] = None,
) -> type["Model"]:
    """
    Generates an `edgy.Model` with all the required definitions to generate the pydantic
    like model.
    """
    from edgy.core.db.models.model import Model

    if not __bases__:
        __bases__ = (Model,)

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
    if not __type_kwargs__:
        __type_kwargs__ = {}

    model: type[Model] = type(__name__, __bases__, core_definitions, **__type_kwargs__)
    return model


def generify_model_fields(model: type["BaseModelType"]) -> dict[Any, Any]:
    """
    Makes all fields generic when a partial model is generated or used.
    This also removes any metadata for the field such as validations making
    it a clean slate to be used internally to process dynamic data and removing
    the constraints of the original model fields.
    """
    fields = {}

    # handle the nested non existing results
    for name, field in model.model_fields.items():
        field.annotation = Any
        # only valid for edgy fields
        with contextlib.suppress(AttributeError):
            field.null = True
        # set a default to fix is_required
        if field.default is PydanticUndefined:
            field.default = None
        field.metadata = []
        fields[name] = field
    return fields
