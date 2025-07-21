from __future__ import annotations

import sys
from typing import Any, ClassVar, cast

from pydantic import ConfigDict

from edgy.core.db.models.base import EdgyBaseModel
from edgy.core.db.models.managers import BaseManager, Manager, RedirectManager
from edgy.core.db.models.metaclasses import BaseModelMeta, MetaInfo
from edgy.core.db.models.mixins.admin import AdminMixin
from edgy.core.db.models.mixins.db import DatabaseMixin
from edgy.core.db.models.mixins.dump import DumpMixin
from edgy.core.db.models.mixins.generics import DeclarativeMixin
from edgy.core.db.models.mixins.reflection import ReflectedModelMixin
from edgy.core.db.models.mixins.row import ModelRowMixin
from edgy.core.utils.models import create_edgy_model, generify_model_fields

if sys.version_info >= (3, 11):  # pragma: no cover
    from typing import Self
else:  # pragma: no cover
    from typing_extensions import Self


class Model(
    ModelRowMixin,
    DeclarativeMixin,
    DatabaseMixin,
    AdminMixin,
    DumpMixin,
    EdgyBaseModel,
    metaclass=BaseModelMeta,
):
    """
    The `Model` class represents an Edgy ORM model, serving as the foundation for
    database table mapping and interactions.

    This class combines various mixins to provide a comprehensive set of functionalities,
    including row-level operations (`ModelRowMixin`), declarative capabilities for
    SQLAlchemy model generation (`DeclarativeMixin`), database connectivity
    (`DatabaseMixin`), administrative features (`AdminMixin`), and data dumping
    capabilities (`DumpMixin`). It inherits from `EdgyBaseModel` for core model
    features and uses `BaseModelMeta` as its metaclass to handle model registration
    and setup.

    Models defined inheriting from this class can be automatically converted into
    SQLAlchemy declarative models, facilitating database schema generation and
    ORM operations.

    Example:
        ```python
        import edgy
        from edgy import Database, Registry

        # Initialize a database connection and a registry for models.
        database = Database("sqlite:///db.sqlite")
        models = Registry(database=database)


        class User(edgy.Model):
            '''
            The User model represents a 'users' table in the database.
            If no table name is explicitly provided in the Meta class,
            Edgy automatically infers it (e.g., "users" from "User").
            '''

            # Define model fields using Edgy's field types.
            id: int = edgy.IntegerField(primary_key=True, autoincrement=True)
            is_active: bool = edgy.BooleanField(default=False)

            class Meta:
                # Associate the model with a registry for database operations.
                registry = models
        ```
    """

    # Type hints for class variables.
    # `proxy_model` stores a shallow copy of the model, used internally.
    proxy_model: ClassVar[type[Self]]
    # `__parent__` stores a reference to a parent model in hierarchical structures, if any.
    __parent__: ClassVar[type[Self] | None]
    # `query` is the default manager for performing database queries.
    query: ClassVar[BaseManager] = Manager()
    # `query_related` is a redirect manager, pointing to the `query` manager for related queries.
    query_related: ClassVar[BaseManager] = RedirectManager(redirect_name="query")
    # `meta` holds metadata about the model, initialized as abstract and not registered by default.
    # registry = False, stops the retrieval of the registry from base classes
    meta: ClassVar[MetaInfo] = MetaInfo(None, abstract=True, registry=False)

    class Meta:
        """
        Inner `Meta` class for configuring model-specific options.

        Attributes:
            abstract (bool): If `True`, the model is considered abstract and will not
                             be created as a database table. Defaults to `True`.
            registry (bool): If `False`, prevents the model from inheriting a registry
                             from its base classes, ensuring it's not automatically
                             added to a global registry unless explicitly specified.
                             Defaults to `False`.
        """

        abstract = True
        # Setting registry to False stops the automatic retrieval of the registry from
        # base classes, allowing for more explicit control over model registration.
        registry = False

    @classmethod
    def real_add_to_registry(cls, **kwargs: Any) -> type[Model]:
        """
        Adds the model to its associated registry, handling admin model registration.

        This method is called during the model's initialization process to register
        it with the `Registry` instance specified in its `Meta` class. It also
        conditionally adds the model to the admin's list of registered models
        if `in_admin` is not `False` and a registry is present.

        Args:
            **kwargs (Any): Arbitrary keyword arguments passed to the superclass method.

        Returns:
            type[Model]: The model class after being added to the registry.
        """
        # Store the current `in_admin` status from the model's meta information.
        in_admin = cls.meta.in_admin
        # Call the superclass method to perform the actual addition to the registry.
        result = cast(type[Model], super().real_add_to_registry(**kwargs))

        # If `in_admin` is not explicitly `False` and a registry is available,
        # add the model's name to the registry's admin_models set.
        if in_admin is not False and result.meta.registry:
            result.meta.registry.admin_models.add(result.__name__)
        return result

    @classmethod
    def generate_proxy_model(cls) -> type[Model]:
        """
        Generates a lightweight proxy model based on the current model.

        A proxy model is a shallow copy of the original model. It is not added to
        the registry and typically has its field references replaced to be generic
        (e.g., `edgy.fields.BigIntegerField` becomes `int`). This is useful for
        internal operations or when a stripped-down version of the model is needed
        without affecting the main registry.

        Returns:
            type[Model]: A new model class representing the proxy model.
        """
        # Initialize a dictionary to hold attributes for the new proxy model.
        # It excludes certain internal pydantic-related keys.
        attrs: dict[str, Any] = {
            key: val for key, val in cls.__dict__.items() if key not in cls._removed_copy_keys
        }

        # Managers and fields are specifically re-added as they are essential
        # for the proxy model's functionality. The 'no_copy' flags are not
        # honored here as it is a specific type of copy for internal use.
        attrs.update(cls.meta.fields)
        attrs.update(cls.meta.managers)
        # Mark this model as a proxy model for internal identification.
        attrs["__is_proxy_model__"] = True

        # Create the new Edgy model using the collected attributes and metadata.
        # `skip_registry` is set to True to ensure this proxy model is not
        # inadvertently added to the global model registry.
        _copy = create_edgy_model(
            __name__=cls.__name__,
            __module__=cls.__module__,
            __definitions__=attrs,
            __metadata__=cls.meta,
            __bases__=cls.__bases__,
            # The registry is still copied from meta but `skip_registry` prevents
            # it from being added to the global registry by the metaclass.
            __type_kwargs__={"skip_registry": True},
        )
        # Assign the database connection from the original model to the proxy model.
        _copy.database = cls.database
        # Convert specific Edgy field types in the proxy model to their generic Python types.
        generify_model_fields(_copy)
        return _copy


class StrictModel(Model):
    """
    A variant of the `Model` class that enforces strict validation rules using Pydantic's
    `ConfigDict`.

    This model will forbid extra fields not defined in the model schema and enable
    strict validation and assignment checks, making it ideal for scenarios where
    data integrity and schema adherence are paramount.
    """

    # Configure Pydantic model settings to enforce strict validation.
    model_config = ConfigDict(
        extra="forbid",  # Forbids any extra fields not defined in the model.
        arbitrary_types_allowed=True,  # Allows arbitrary types for fields.
        validate_assignment=True,  # Enables validation during attribute assignment.
        strict=True,  # Enforces strict type checking.
    )

    class Meta:
        """
        Inner `Meta` class for configuring `StrictModel` specific options.

        Attributes:
            abstract (bool): If `True`, the model is considered abstract and will not
                             be created as a database table. Defaults to `True`.
            registry (bool): If `False`, prevents the model from inheriting a registry
                             from its base classes, ensuring it's not automatically
                             added to a global registry unless explicitly specified.
                             Defaults to `False`.
        """

        abstract = True
        # Setting registry to False stops the automatic retrieval of the registry from
        # base classes, allowing for more explicit control over model registration.
        registry = False


class ReflectModel(ReflectedModelMixin, Model):
    """
    A specialized `Model` class designed for reflecting existing database tables.

    This model extends the base `Model` with `ReflectedModelMixin`, enabling it
    to introspect and map to an existing table in a database. Reflection on async
    database engines is not directly supported by underlying libraries, therefore,
    it typically requires a synchronous engine call for the reflection process.
    """

    class Meta:
        """
        Inner `Meta` class for configuring `ReflectModel` specific options.

        Attributes:
            abstract (bool): If `True`, the model is considered abstract and will not
                             be created as a database table. Defaults to `True`.
            registry (bool): If `False`, prevents the model from inheriting a registry
                             from its base classes, ensuring it's not automatically
                             added to a global registry unless explicitly specified.
                             Defaults to `False`.
        """

        abstract = True
        # Setting registry to False stops the automatic retrieval of the registry from
        # base classes, allowing for more explicit control over model registration.
        registry = False
