from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    # TYPE_CHECKING is preserved as per instruction.
    # MetaInfo is likely used for `cls.meta.registry.declarative_base`
    # and `cls.meta.fields`.
    from edgy.core.db.models.model import EdgyBaseModel


class DeclarativeMixin:
    """
    A mixin class designed to integrate Edgy models with SQLAlchemy's Declarative system.

    This mixin provides methods to transform an Edgy model's underlying SQLAlchemy Core
    Table representation into a full SQLAlchemy Declarative model. This allows Edgy
    models to be used seamlessly within contexts that expect SQLAlchemy Declarative
    Base models, enabling advanced features like ORM relationships.

    Attributes:
        meta: A ClassVar of type `MetaInfo` (inferred from usage), providing access
              to model metadata, including the SQLAlchemy Table object and field definitions.
    """

    # This attribute is typically provided by the Edgy model's metaclass.
    meta: Any
    """
    Metadata object associated with the Edgy model, containing configuration details
    such as the SQLAlchemy Table object, field definitions, and the declarative base
    registry.
    """

    @classmethod
    def declarative(cls: type[EdgyBaseModel]) -> Any:
        """
        Returns the SQLAlchemy Declarative model representation of the Edgy model.

        This is a convenience class method that acts as an entry point to obtain
        the declarative version of the current Edgy model. It delegates the actual
        transformation process to `generate_model_declarative`.

        Args:
            cls: The Edgy model class (e.g., `User`, `Product`) for which the
                 declarative model is to be generated.

        Returns:
            An `Any` type representing the dynamically generated SQLAlchemy Declarative
            model class, which can then be used with SQLAlchemy ORM functionalities.
        """
        # Calls the internal method to perform the transformation.
        return cls.generate_model_declarative()

    @classmethod
    def generate_model_declarative(cls: type[EdgyBaseModel]) -> Any:
        """
        Transforms an Edgy model's SQLAlchemy Core Table into an SQLAlchemy Declarative model.

        This method dynamically creates a new class that inherits from SQLAlchemy's
        Declarative Base. It assigns the Edgy model's SQLAlchemy Core Table to the
        `__table__` attribute of the new class, making it a declarative model.
        Additionally, it identifies and configures SQLAlchemy ORM relationships
        for any foreign key fields defined in the Edgy model.

        Args:
            cls: The Edgy model class (e.g., `User`, `Product`) to be converted
                 into a SQLAlchemy Declarative model.

        Returns:
            An `Any` type representing the dynamically generated SQLAlchemy Declarative
            model class, complete with mapped relationships.
        """
        # orm is heavy, so keep it in the function
        from sqlalchemy.orm import Mapped, relationship

        # Retrieve the declarative base from the Edgy model's metadata registry.
        # This `Base` is the foundation for the new declarative model.
        Base = cls.meta.registry.declarative_base  # type: ignore

        # Define a dictionary to hold the attributes for the new declarative model class.
        # The `__table__` attribute is crucial for linking the declarative model
        # to the existing SQLAlchemy Core Table defined by Edgy.
        fields: dict[str, Any] = {"__table__": cls.table}

        # Dynamically create the new declarative model class using `type()`.
        # The class name is derived from the original Edgy model's name.
        model_table = type(cls.__name__, (Base,), fields)

        # Iterate through all columns in the Edgy model's SQLAlchemy Core Table.
        # This loop identifies foreign key columns that need corresponding ORM relationships.
        for column in cls.table.columns:
            # Skip columns that do not have foreign key constraints.
            if not column.foreign_keys:
                continue

            # Retrieve the field definition from the Edgy model's metadata using the column name.
            field = cls.meta.fields.get(column.name)

            # Determine the target model's name for the relationship.
            # If `field.to` is a class, use its name; otherwise, use `field.to` directly.
            to: str = field.to.__name__ if inspect.isclass(field.to) else field.to

            # Create an SQLAlchemy ORM relationship.
            # `Mapped[to]` provides type hinting for the relationship.
            # `relationship(to)` establishes the ORM link to the target model.
            mapped_model: Mapped[Any] = relationship(to)
            # The `type: ignore` is used because `Mapped[to]` expects a class,
            # but `to` is a string here. SQLAlchemy handles this internally.

            # Add the newly created relationship as a property to the declarative model's mapper.
            # The property name is constructed by appending `_relation` to the column name,
            # ensuring a distinct name for the ORM relationship attribute.
            model_table.__mapper__.add_property(f"{column.name}_relation", mapped_model)

        # Return the fully constructed SQLAlchemy Declarative model class.
        return model_table
