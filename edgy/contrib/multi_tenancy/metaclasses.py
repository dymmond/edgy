from typing import Any, Optional, cast

from edgy.core.db.models.metaclasses import (
    BaseModelMeta,
    MetaInfo,
)


def _check_model_inherited_tenancy(bases: tuple[type, ...]) -> bool:
    for base in bases:
        meta: Optional[MetaInfo] = getattr(base, "meta", None)
        if meta is None:
            continue
        if hasattr(meta, "is_tenant"):
            return cast(bool, meta.is_tenant)

    return False


class TenantMeta(MetaInfo):
    __slots__ = ("is_tenant", "register_default")
    register_default: bool

    def __init__(self, meta: Any = None, **kwargs: Any) -> None:
        self.is_tenant = getattr(meta, "is_tenant", None)
        # register in models too, so there is a default
        # otherwise they only exist as tenant models
        self.register_default: bool = getattr(meta, "register_default", True)

        # must be last
        super().__init__(meta, **kwargs)

    def set_tenant(self, is_tenant: bool) -> None:
        self.is_tenant = is_tenant


class BaseTenantMeta(BaseModelMeta):
    """
    The metaclass for the base tenant used by the Edgy contrib mixin.

    This should only be used by the contrib or if you decided to use
    your own tenant model using the `is_tenant` inside the `Meta` object.
    """

    def __new__(cls, name: str, bases: tuple[type, ...], attrs: Any, **kwargs: Any) -> Any:
        new_model = super().__new__(cls, name, bases, attrs, meta_info_class=TenantMeta, **kwargs)
        if new_model.meta.is_tenant is None:
            new_model.meta.is_tenant = _check_model_inherited_tenancy(bases)

        if (
            new_model.meta.registry
            and new_model.meta.is_tenant
            and not new_model.meta.abstract
            and not new_model.__is_proxy_model__
        ):
            assert (
                new_model.__reflected__ is False
            ), "Reflected models are not compatible with multi_tenancy"

            if not new_model.meta.register_default:
                # remove from models
                new_model.meta.registry.models.pop(new_model.__name__, None)
            new_model.meta.registry.tenant_models[new_model.__name__] = new_model
        return new_model
