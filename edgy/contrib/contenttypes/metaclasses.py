from typing import Any, Dict, Tuple, Type

from edgy.core.db.models.metaclasses import (
    BaseModelMeta,
)


class ContentTypeMeta(BaseModelMeta):
    def __new__(
        cls, name: str, bases: Tuple[Type, ...], attrs: Dict[str, Any], **kwargs: Any
    ) -> Any:
        new_model = super().__new__(cls, name, bases, attrs, **kwargs)
        if new_model.no_constraint:
            new_model.__require_model_based_deletion__ = True
        return new_model
