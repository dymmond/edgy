from typing import TYPE_CHECKING, Any, ClassVar

import edgy

from .metaclasses import AutoReflectionMeta, AutoReflectionMetaInfo

if TYPE_CHECKING:
    from edgy.core.db.models.types import BaseModelType


class AutoReflectModel(edgy.ReflectModel, metaclass=AutoReflectionMeta):
    meta: ClassVar[AutoReflectionMetaInfo]

    @classmethod
    def real_add_to_registry(cls, **kwargs: Any) -> type["BaseModelType"]:
        if isinstance(cls.meta, AutoReflectionMetaInfo):
            kwargs.setdefault("registry_type_name", "pattern_models")
        return super().real_add_to_registry(**kwargs)
