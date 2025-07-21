from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

import edgy

from .metaclasses import AutoReflectionMeta, AutoReflectionMetaInfo

if TYPE_CHECKING:
    from edgy.core.db.models.types import BaseModelType


class AutoReflectModel(edgy.ReflectModel, metaclass=AutoReflectionMeta):
    """
    A base model for automatic reflection of database tables into Edgy models.

    This class extends `edgy.ReflectModel` and uses `AutoReflectionMeta`
    to enable dynamic schema introspection and model generation.
    It provides a mechanism to automatically add reflected models to a
    specific registry type, typically for pattern-based model discovery.
    """

    meta: ClassVar[AutoReflectionMetaInfo]
    """
    The `MetaInfo` object for this model, specifically typed as
    `AutoReflectionMetaInfo` to support auto-reflection properties.
    """

    @classmethod
    def real_add_to_registry(cls, **kwargs: Any) -> type[BaseModelType]:
        """
        Adds the current model class to the Edgy registry.

        This class method overrides the default `real_add_to_registry` to
        ensure that if the model's meta information is of type
        `AutoReflectionMetaInfo`, it is added to the "pattern_models"
        registry type by default. This is useful for grouping automatically
        reflected models.

        Args:
            **kwargs (Any): Arbitrary keyword arguments to pass to the
                            parent's `real_add_to_registry` method.

        Returns:
            type[BaseModelType]: The model class that has been added to the registry.
        """
        # Check if the model's meta is an instance of AutoReflectionMetaInfo.
        if isinstance(cls.meta, AutoReflectionMetaInfo):
            # If it is, set the default 'registry_type_name' to "pattern_models".
            # This ensures that auto-reflected models are registered under this specific type,
            # allowing for easier management and querying of dynamically created models.
            kwargs.setdefault("registry_type_name", "pattern_models")
        # Call the parent's `real_add_to_registry` method to complete the registration.
        return super().real_add_to_registry(**kwargs)
