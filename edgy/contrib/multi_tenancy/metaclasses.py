from typing import TYPE_CHECKING, Any, Literal, Optional, Union, cast

from edgy.core.db.models.metaclasses import (
    BaseModelMeta,
    MetaInfo,
)

if TYPE_CHECKING:
    from edgy.core.connection.database import Database


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

    def __new__(
        cls,
        name: str,
        bases: tuple[type, ...],
        attrs: Any,
        on_conflict: Literal["error", "replace", "keep"] = "error",
        skip_registry: Union[bool, Literal["allow_search"]] = False,
        meta_info_class: type[TenantMeta] = TenantMeta,
        **kwargs: Any,
    ) -> Any:
        database: Union[Literal["keep"], None, Database, bool] = attrs.get("database", "keep")
        new_model = super().__new__(
            cls,
            name,
            bases,
            attrs,
            skip_registry="allow_search",
            meta_info_class=meta_info_class,
            **kwargs,
        )
        if new_model.meta.is_tenant is None:
            new_model.meta.is_tenant = _check_model_inherited_tenancy(bases)

        if (
            not skip_registry
            and new_model.meta.registry
            and not new_model.meta.abstract
            and not new_model.__is_proxy_model__
        ):
            new_model.add_to_registry(
                new_model.meta.registry, on_conflict=on_conflict, database=database
            )
        return new_model
