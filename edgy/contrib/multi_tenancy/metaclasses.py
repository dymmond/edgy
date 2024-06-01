from typing import Any, Optional, Tuple, Type, Union

from edgy.core.db.models.metaclasses import (
    BaseModelMeta,
    MetaInfo,
    get_model_registry,
)
from edgy.exceptions import ImproperlyConfigured


def _check_model_inherited_tenancy(bases: Tuple[Type, ...]) -> Union[bool, None]:
    """
    When a registry is missing from the Meta class, it should look up for the bases
    and obtain the first found registry.

    If not found, then a ImproperlyConfigured exception is raised.
    """
    is_tenant: Optional[bool] = None

    for base in bases:
        meta: MetaInfo = getattr(base, "meta", None)  # type: ignore
        if not meta:
            continue

        meta_tenant: Optional[bool] = getattr(meta, "is_tenant", None)
        if meta_tenant is not None and meta_tenant is not False:
            is_tenant = meta_tenant
            break

    return is_tenant


class TenantMeta(MetaInfo):
    def __init__(self, meta: Any = None, **kwargs: Any) -> None:
        super().__init__(meta, **kwargs)
        self.is_tenant: bool = getattr(meta, "is_tenant", False)

    def set_tenant(self, is_tenant: bool) -> None:
        self.is_tenant = is_tenant


class BaseTenantMeta(BaseModelMeta):
    """
    The metaclass for the base tenant used by the Edgy contrib mixin.

    This should only be used by the contrib or if you decided to use
    your own tenant model using the `is_tenant` inside the `Meta` object.
    """

    def __new__(cls, name: str, bases: Tuple[Type, ...], attrs: Any) -> Any:
        meta_class: object = attrs.get("Meta", type("Meta", (), {}))
        new_model = super().__new__(cls, name, bases, attrs)
        meta: TenantMeta = TenantMeta(new_model.meta)

        if hasattr(meta_class, "is_tenant"):
            meta.set_tenant(meta_class.is_tenant)

        # Handle the registry of models
        if getattr(meta, "registry", None) is None:
            if hasattr(new_model, "__db_model__") and new_model.__db_model__:
                meta.registry = get_model_registry(bases)
            else:
                return new_model
        registry = meta.registry
        if registry is None:
            raise ImproperlyConfigured(
                "Registry for the table not found in the Meta class or any of the superclasses. You must set the registry in the Meta."
            )

        new_model.meta = meta

        # Check if is tenant
        is_tenant = _check_model_inherited_tenancy(bases)
        if is_tenant:
            new_model.meta.is_tenant = is_tenant

        if registry:
            try:
                if meta.is_tenant and not meta.abstract:
                    registry.tenant_models[new_model.__name__] = new_model
            except KeyError:
                ...  # pragma: no cover
        return new_model
