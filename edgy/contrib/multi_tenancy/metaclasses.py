from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, cast

from edgy.core.db.models.metaclasses import BaseModelMeta, MetaInfo, get_model_meta_attr

if TYPE_CHECKING:
    from edgy.core.connection.database import Database


def _check_model_inherited_tenancy(bases: tuple[type, ...]) -> bool:
    """
    Checks if any of the base classes of a model have a `MetaInfo`
    object with `is_tenant` set to True.

    Args:
        bases (tuple[type, ...]): A tuple of base classes to check.

    Returns:
        bool: True if `is_tenant` is found and set to True in any base class's MetaInfo,
              False otherwise.
    """
    for base in bases:
        # Get the 'meta' attribute from the base class, if it exists.
        meta: MetaInfo | None = getattr(base, "meta", None)
        if meta is None:
            # If there's no 'meta' attribute, continue to the next base class.
            continue
        if hasattr(meta, "is_tenant"):
            # If 'is_tenant' attribute exists in 'meta', return its boolean value.
            return cast(bool, meta.is_tenant)

    # If no base class has 'is_tenant' set to True in its MetaInfo, return False.
    return False


class TenantMeta(MetaInfo):
    """
    A `MetaInfo` subclass specifically designed for tenant-aware models in Edgy.

    This class extends `MetaInfo` by adding attributes relevant to multi-tenancy,
    such as `is_tenant` to mark a model as a tenant model and `register_default`
    to control whether a tenant model should also be registered as a default model.
    """

    __slots__ = ("is_tenant", "register_default")
    register_default: bool | None

    def __init__(self, meta: Any = None, **kwargs: Any) -> None:
        """
        Initializes the `TenantMeta` instance.

        Args:
            meta (Any, optional): An existing `MetaInfo` object or an object
                                  with `is_tenant` and `register_default`
                                  attributes to copy values from. Defaults to None.
            **kwargs (Any): Additional keyword arguments to pass to the
                            `MetaInfo` parent constructor.
        """
        # Initialize 'is_tenant' from the provided 'meta' object, or set to None.
        self.is_tenant = getattr(meta, "is_tenant", None)
        # Initialize 'register_default' from the provided 'meta' object.
        # This controls whether the tenant model also gets registered as a
        # default model, allowing it to exist independently of tenancy.
        self.register_default = getattr(meta, "register_default", None)

        # Call the parent constructor as the last step to ensure proper initialization
        # of inherited MetaInfo attributes.
        super().__init__(meta, **kwargs)

    def set_tenant(self, is_tenant: bool) -> None:
        """
        Sets the `is_tenant` flag for the current `TenantMeta` instance.

        Args:
            is_tenant (bool): A boolean value indicating whether the model
                              is a tenant model (True) or not (False).
        """
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
        skip_registry: bool | Literal["allow_search"] = False,
        meta_info_class: type[TenantMeta] = TenantMeta,
        **kwargs: Any,
    ) -> type:
        """
        Creates a new model class with tenant-specific metadata.

        Args:
            cls (type): The metaclass itself.
            name (str): The name of the new model class.
            bases (tuple[type, ...]): A tuple of base classes for the new model.
            attrs (Any): A dictionary of attributes and methods for the new model class.
            on_conflict (Literal["error", "replace", "keep"], optional): Strategy
                to handle conflicts when registering the model in the registry.
                Defaults to "error".
            skip_registry (bool | Literal["allow_search"], optional): If True,
                the model will not be added to the registry. If "allow_search",
                it will be added but not considered for direct creation.
                Defaults to False.
            meta_info_class (type[TenantMeta], optional): The `MetaInfo` class
                to use for the new model. Defaults to `TenantMeta`.
            **kwargs (Any): Additional keyword arguments.

        Returns:
            type: The newly created model class.
        """
        # Retrieve the 'database' attribute from attrs, defaulting to "keep" if not present.
        database: Literal["keep"] | None | Database | bool = attrs.get("database", "keep")
        # Call the parent's __new__ method to create the initial model class.
        new_model = super().__new__(
            cls,
            name,
            bases,
            attrs,
            skip_registry="allow_search",  # Always allow search for tenant models.
            meta_info_class=meta_info_class,
            **kwargs,
        )
        # Set the 'is_tenant' attribute on the new model's meta,
        # inheriting from bases if defined.
        new_model.meta.is_tenant = get_model_meta_attr("is_tenant", bases, new_model.meta)
        # Set the 'register_default' attribute on the new model's meta,
        # inheriting from bases if defined.
        new_model.meta.register_default = get_model_meta_attr(
            "register_default", bases, new_model.meta
        )

        # Check if the model should be added to the registry.
        # It should not be skipped, should have a registry, not be abstract,
        # and not be a proxy model.
        if (
            not skip_registry
            and new_model.meta.registry
            and not new_model.meta.abstract
            and not new_model.__is_proxy_model__
        ):
            # Add the new model to the registry with the specified conflict resolution
            # and database.
            new_model.add_to_registry(
                new_model.meta.registry, on_conflict=on_conflict, database=database
            )
        # Return the newly created and configured model class.
        return new_model
