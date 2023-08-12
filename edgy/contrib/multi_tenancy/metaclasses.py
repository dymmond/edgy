from typing import TYPE_CHECKING, Any, Tuple, Type

from edgy.core.db.models.metaclasses import BaseModelMeta, MetaInfo

if TYPE_CHECKING:
    pass


class TenantMeta(MetaInfo):
    def __init__(self, meta: Any = None, **kwargs: Any) -> None:
        super().__init__(meta, **kwargs)
        self.is_tenant: bool = getattr(meta, "is_tenant", False)


class BaseTenantMeta(BaseModelMeta):
    def __new__(cls, name: str, bases: Tuple[Type, ...], attrs: Any) -> Any:
        meta_class: "object" = attrs.get("Meta", type("Meta", (), {}))
        meta = TenantMeta(meta_class)
        attrs["meta"] = meta
        new_model = super().__new__(cls, name, bases, attrs)

        registry = new_model.meta.registry

        if registry:
            try:
                if meta.is_tenant:
                    registry.tenant_models[new_model.__name__] = new_model
            except KeyError:
                ...  # pragma: no cover

        return new_model
