from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from edgy.contrib.multi_tenancy.metaclasses import BaseTenantMeta, TenantMeta
from edgy.core.db.models.model import Model

if TYPE_CHECKING:
    from edgy.core.db.models.types import BaseModelType


class TenantModel(Model, metaclass=BaseTenantMeta):
    """
    Base for a multi-tenant model from the Edgy contrib.

    This class provides a foundational structure for models that need to
    support multi-tenancy within an Edgy application. While not mandatory,
    it offers an out-of-the-box solution for implementing multi-tenancy
    in a straightforward manner.

    This design serves as an example of how to achieve multi-tenancy
    using Edgy's model capabilities, rather than being the exclusive approach.

    Key Features:
    - Uses `BaseTenantMeta` as its metaclass to handle tenant-specific
      model registration and behavior.
    - Provides a `meta` ClassVar for `TenantMeta` configurations, allowing
      for abstract tenant models.
    - Overrides `real_add_to_registry` to manage the registration of
      tenant-aware models within the Edgy registry.
    """

    meta: ClassVar[TenantMeta] = TenantMeta(None, abstract=True)
    """
    A class variable holding the `TenantMeta` instance for this model.

    This `meta` object allows defining tenant-specific configurations,
    such as whether a model is a tenant model, and whether it should
    be registered in the default registry in addition to the tenant registry.
    It is marked as `abstract=True` for this base class, meaning no table
    will be created for `TenantModel` itself.
    """

    @classmethod
    def real_add_to_registry(cls, **kwargs: Any) -> type[BaseModelType]:
        """
        Overrides the default `real_add_to_registry` method from `edgy.Model`.

        This method is called during model initialization and registration
        with the database registry. For `TenantModel` and its concrete
        subclasses, it customizes the registration process to ensure that
        tenant-aware models are correctly handled within the multi-tenancy
        system.

        Specifically, it registers the model with the tenant-specific registry
        (`cls.meta.registry.tenant_models`) and, optionally, removes it from
        the default registry if `register_default` is set to `False` in the
        `TenantMeta`.

        Args:
            **kwargs (Any): Arbitrary keyword arguments passed during registration.

        Returns:
            type["BaseModelType"]: The class itself, after being added to the registry.

        Raises:
            AssertionError: If a reflected model is used with multi-tenancy,
                as reflected models are currently not compatible with this setup.
        """
        # Call the superclass method to perform standard model registration first.
        result = super().real_add_to_registry(**kwargs)

        # Check conditions for tenant-specific registration:
        # 1. `cls.meta.registry` exists (meaning a registry is available).
        # 2. `cls.meta.is_tenant` is True (model is marked as tenant-aware).
        # 3. `cls.meta.abstract` is False (it's a concrete model, not abstract).
        # 4. `cls.__is_proxy_model__` is False (it's not a proxy model).
        if (
            cls.meta.registry
            and cls.meta.is_tenant
            and not cls.meta.abstract
            and not cls.__is_proxy_model__
        ):
            # Reflected models are not supported with multi-tenancy.
            assert cls.__reflected__ is False, (
                "Reflected models are not compatible with multi_tenancy"
            )

            # If `register_default` is False in TenantMeta, remove the model
            # from the default global registry to ensure it's only managed
            # by the tenant-specific mechanism.
            if cls.meta.register_default is False:
                cls.meta.registry.models.pop(cls.__name__, None)

            # Register the model in the tenant-specific models dictionary.
            cls.meta.registry.tenant_models[cls.__name__] = cls

        return result
