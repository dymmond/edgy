from __future__ import annotations

from typing import Any

from edgy.core.db.models.metaclasses import BaseModelMeta


class ContentTypeMeta(BaseModelMeta):
    """
    Metaclass for ContentType models in Edgy.

    This metaclass extends `BaseModelMeta` to provide specific behaviors
    for models intended to represent content types. It primarily ensures
    that if a content type model is defined without database constraints,
    deletion operations are handled at the model level rather than relying
    solely on database cascade rules.
    """

    def __new__(
        cls, name: str, bases: tuple[type, ...], attrs: dict[str, Any], **kwargs: Any
    ) -> type:
        """
        Creates a new ContentType model class.

        Args:
            cls (type): The metaclass itself.
            name (str): The name of the new model class.
            bases (tuple[type, ...]): A tuple of base classes for the new model.
            attrs (dict[str, Any]): A dictionary of attributes and methods
                                    for the new model class.
            **kwargs (Any): Additional keyword arguments to pass to the
                            `BaseModelMeta` constructor.

        Returns:
            type: The newly created model class.
        """
        # Call the parent's __new__ method to create the initial model class.
        new_model = super().__new__(cls, name, bases, attrs, **kwargs)

        # If the new model is configured to have "no_constraint" (i.e., no
        # database-level foreign key constraints), then set a flag
        # "__require_model_based_deletion__" to True.
        # This flag indicates that deletion logic for related objects
        # needs to be handled explicitly at the application/model level
        # rather than relying on database cascade actions, as there is no
        # database constraint to enforce them.
        if new_model.no_constraint:
            new_model.__require_model_based_deletion__ = True
        return new_model
