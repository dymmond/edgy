from typing import Any, Tuple, Type

from edgy.core.db.models.metaclasses import BaseModelMeta, MetaInfo


class TenantMeta(MetaInfo):
    def __init__(self, meta: Any = None, **kwargs: Any) -> None:
        super().__init__(meta, **kwargs)
        self.is_tenant: bool = getattr(meta, "is_tenant", False)


class BaseTenantMeta(BaseModelMeta):
    meta_info: "TenantMeta" = TenantMeta(None)

    def __new__(cls, name: str, bases: Tuple[Type, ...], attrs: Any) -> Any:
        meta_class: "object" = attrs.get("Meta", type("Meta", (), {}))
        meta = TenantMeta(meta_class)
        attrs["Meta"] = meta
        new_model = super().__new__(cls, name, bases, attrs)

        cls.meta_info = meta
        registry = new_model.meta.registry

        if registry:
            try:
                if meta.is_tenant:
                    registry.tenant_models[new_model.__name__] = new_model
            except KeyError:
                ...  # pragma: no cover

        return new_model

    def is_tenant_model(cls) -> bool:
        """
        Checks if this is a tenant model.

        The schema is only built if the model is a tenant
        """
        return bool(cls.meta_info.is_tenant)

    def table_schema(cls, schema: str) -> Any:
        """
        Making sure the tables on inheritance state, creates the new
        one properly.

        The use of context vars instead of using the lru_cache comes from
        a warning from `ruff` where lru can lead to memory leaks.
        """
        if cls.is_tenant_model():
            return cls.build(schema)
        return cls.build()
