from typing import TYPE_CHECKING, Any, ClassVar

from edgy.contrib.multi_tenancy.metaclasses import BaseTenantMeta, TenantMeta
from edgy.core.db.models.model import Model

if TYPE_CHECKING:
    from edgy.core.db.models.types import BaseModelType


class TenantModel(Model, metaclass=BaseTenantMeta):
    """
    Base for a multi tenant model from the Edgy contrib.
    This is **not mandatory** and can be used as a possible
    out of the box solution for multi tenancy.

    This design is not meant to be "the one" but instead an
    example of how to achieve the multi-tenancy in a simple fashion
    using Edgy and Edgy models.
    """

    meta: ClassVar[TenantMeta] = TenantMeta(None, abstract=True)

    @classmethod
    def real_add_to_registry(cls, **kwargs: Any) -> type["BaseModelType"]:
        result = super().real_add_to_registry(**kwargs)

        if (
            cls.meta.registry
            and cls.meta.is_tenant
            and not cls.meta.abstract
            and not cls.__is_proxy_model__
        ):
            assert cls.__reflected__ is False, (
                "Reflected models are not compatible with multi_tenancy"
            )

            if not cls.meta.register_default:
                # remove from models
                cls.meta.registry.models.pop(cls.__name__, None)
            cls.meta.registry.tenant_models[cls.__name__] = cls

        return result
