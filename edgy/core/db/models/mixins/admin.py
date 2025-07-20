from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from pydantic import ConfigDict

# Leverage lazy imports to break circular imports.
from edgy.core import marshalls

if TYPE_CHECKING:
    from edgy.core.db.models import Model


class AdminMixin:
    """
    A mixin class providing administrative functionalities and configurations
    for Edgy models.

    This class offers methods to generate marshall configurations and marshall
    classes specifically tailored for administrative interfaces, allowing
    dynamic adjustments based on the operation phase (e.g., create, update)
    and whether the configuration is for a schema or an instance.
    """

    @classmethod
    def get_admin_marshall_config(
        cls: type[Model], *, phase: str, for_schema: bool
    ) -> dict[str, Any]:
        """
        Generates a dictionary representing the marshall configuration for
        the admin interface.

        This configuration dictates how model fields are handled during different
        administrative operations (e.g., creation, update) and schema generation.

        Args:
            cls: The Edgy Model class for which the marshall configuration is
                being generated.
            phase: The current phase of the administrative operation, typically
                'create', 'update', or 'read'. This influences field exclusions
                and read-only states.
            for_schema: A boolean indicating whether the configuration is
                intended for schema generation (e.g., OpenAPI documentation)
                or for actual data marshalling.

        Returns:
            A dictionary containing the marshall configuration, including
            specifications for fields, read-only exclusions, primary key
            read-only status, and autoincrement exclusions.
        """
        return {
            "fields": ["__all__"],  # Include all fields by default.
            # Exclude read-only fields during 'create' or 'update' phases.
            "exclude_read_only": phase in {"create", "update"},
            # Primary key is read-only unless in the 'create' phase.
            "primary_key_read_only": phase != "create",
            # Exclude autoincrement fields only when creating a new instance.
            "exclude_autoincrement": phase == "create",
        }

    @classmethod
    def get_admin_marshall_class(
        cls: type[Model], *, phase: str, for_schema: bool = False
    ) -> type[marshalls.Marshall]:
        """
        Generates a dynamic Marshall class specifically for the admin interface.

        This allows for custom marshalling behavior based on the current
        administrative operation phase and whether it's for schema generation.

        Args:
            cls: The Edgy Model class for which the admin marshall class is
                being generated.
            phase: The current phase of the administrative operation (e.g.,
                'create', 'update', 'read'). This phase is used to configure
                the underlying marshall_config.
            for_schema: A boolean indicating whether the generated marshall
                class is intended for schema generation. If True, additional
                properties are forbidden, aligning with strict schema definitions.

        Returns:
            A dynamically created subclass of `marshalls.Marshall` configured
            with the appropriate `ConfigDict` and `marshall_config` for the
            admin interface.
        """

        class AdminMarshall(marshalls.Marshall):
            # Configure Pydantic model behavior.
            # 'title' is set to the model's name for clarity in schemas.
            # 'extra="forbid"' prevents unknown fields when generating schemas.
            model_config: ClassVar[ConfigDict] = ConfigDict(
                title=cls.__name__, extra="forbid" if for_schema else None
            )
            # Initialize the marshall configuration using the model and
            # the admin-specific configuration.
            marshall_config = marshalls.ConfigMarshall(
                model=cls,
                **cls.get_admin_marshall_config(phase=phase, for_schema=for_schema),  # type: ignore
            )

        return AdminMarshall

    @classmethod
    def get_admin_marshall_for_save(
        cls: type[Model], instance: Model | None = None, /, **kwargs: Any
    ) -> marshalls.Marshall:
        """
        Generates a Marshall instance for saving (creating or updating)
        an Edgy model through the admin interface.

        This method determines the appropriate phase ('create' or 'update')
        based on whether an instance is provided, and then creates a
        corresponding `AdminMarshall` instance.

        Args:
            cls: The Edgy Model class for which the marshall instance is
                being generated.
            instance: An optional existing model instance. If provided, the
                operation is considered an 'update'; otherwise, it's a 'create'.
            kwargs: Additional keyword arguments to pass to the `AdminMarshall`
                constructor.

        Returns:
            An instance of `AdminMarshall` prepared for either creating a new
            model record or updating an existing one.
        """
        # Determine the phase based on whether an instance is provided.
        # If an instance exists, it's an 'update' operation; otherwise, it's 'create'.
        phase = "update" if instance is not None else "create"
        # Get the appropriate AdminMarshall class for the determined phase.
        # 'for_schema' is set to False as this is for an instance, not a schema.
        AdminMarshallClass = cls.get_admin_marshall_class(phase=phase, for_schema=False)
        # Return an instance of the AdminMarshallClass, passing the model instance
        # and any additional keyword arguments.
        return AdminMarshallClass(instance, **kwargs)
