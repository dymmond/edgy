from typing import Any, Tuple, Type

from edgy.core.db.models.metaclasses import BaseModelMeta, MetaInfo


class TenantMeta(MetaInfo):
    def __init__(self, meta: Any = None, **kwargs: Any) -> None:
        super().__init__(meta, **kwargs)
        self.is_tenant: bool = getattr(meta, "is_tenant", False)


class BaseTenantMeta(BaseModelMeta):
    def __new__(cls, name: str, bases: Tuple[Type, ...], attrs: Any) -> Any:
        new_model = super().__new__(cls, name, bases, attrs)

        registry = new_model.meta.registry
        meta: "TenantMeta" = TenantMeta(meta=new_model.meta)
        setattr(registry, "tenant_models", {})

        # Remove the reflected models from the registry
        # Add the reflecte model to the views section of the refected
        if registry:
            try:
                if meta.is_tenant:
                    registry.reflected[new_model.__name__] = new_model
            except KeyError:
                ...  # pragma: no cover

        return new_model
