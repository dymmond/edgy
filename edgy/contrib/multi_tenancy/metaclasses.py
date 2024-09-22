from typing import Any, Optional, Tuple, Type, cast

from edgy.core.db.models.metaclasses import (
    BaseModelMeta,
    MetaInfo,
    get_model_registry,
)
from edgy.exceptions import ImproperlyConfigured


def _check_model_inherited_tenancy(bases: Tuple[Type, ...]) -> bool:
    for base in bases:
        meta: Optional[MetaInfo] = getattr(base, "meta", None)
        if meta is None:
            continue
        if hasattr(meta, "is_tenant"):
            return cast(bool, meta.is_tenant)

    return False


class TenantMeta(MetaInfo):
    __slots__ = ("is_tenant", "register_default")

    def __init__(self, meta: Any = None, **kwargs: Any) -> None:
        self.is_tenant: bool = getattr(meta, "is_tenant", False)
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

    def __new__(cls, name: str, bases: Tuple[Type, ...], attrs: Any, **kwargs: Any) -> Any:
        meta_class: object = attrs.get("Meta", type("Meta", (), {}))
        new_model = super().__new__(cls, name, bases, attrs, **kwargs)
        new_model.meta = meta = TenantMeta(new_model.meta)

        if hasattr(meta_class, "is_tenant"):
            meta.is_tenant = cast(bool, meta_class.is_tenant)
        else:
            meta.is_tenant = _check_model_inherited_tenancy(bases)

        if hasattr(meta_class, "register_default"):
            meta.register_default = cast(bool, meta_class.register_default)

        # Handle the registry of models
        if getattr(meta, "registry", None) is None:
            if getattr(new_model, "__db_model__", False):
                meta.registry = get_model_registry(bases)
            else:
                return new_model
        registry = meta.registry
        if registry is None:
            raise ImproperlyConfigured(
                "Registry for the table not found in the Meta class or any of the superclasses. You must set the registry in the Meta."
            )

        if registry and meta.is_tenant and not meta.abstract and not new_model.__is_proxy_model__:
            assert (
                new_model.__reflected__ is False
            ), "Reflected models are not compatible with multi_tenancy"

            if not meta.register_default:
                # remove from models
                registry.models.pop(new_model.__name__, None)
            registry.tenant_models[new_model.__name__] = new_model
        return new_model
