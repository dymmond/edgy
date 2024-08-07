import inspect
from typing import Any

from sqlalchemy.orm import Mapped, relationship


class DeclarativeMixin:
    """
    Mixin for declarative base models.
    """

    @classmethod
    def declarative(cls) -> Any:
        return cls.generate_model_declarative()

    @classmethod
    def generate_model_declarative(cls) -> Any:
        """
        Transforms a core Edgy table into a Declarative model table.
        """
        Base = cls.meta.registry.declarative_base

        # Build the original table
        fields = {"__table__": cls.table}

        # Generate base
        model_table = type(cls.__name__, (Base,), fields)

        # Make sure if there are foreignkeys, builds the relationships
        for column in cls.table.columns:
            if not column.foreign_keys:
                continue

            # Maps the relationships with the foreign keys and related names
            field = cls.meta.fields.get(column.name)
            to = field.to.__name__ if inspect.isclass(field.to) else field.to
            mapped_model: Mapped[to] = relationship(to)  # type: ignore

            # Adds to the current model
            model_table.__mapper__.add_property(f"{column.name}_relation", mapped_model)

        return model_table
