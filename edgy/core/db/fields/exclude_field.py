from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic.json_schema import SkipJsonSchema

from edgy.core.db.context_vars import CURRENT_PHASE
from edgy.core.db.fields.factories import FieldFactory

if TYPE_CHECKING:
    from edgy.core.db.fields.types import BaseFieldType
    from edgy.core.db.models.types import BaseModelType


class ExcludeField(FieldFactory, type[None]):
    """
    A special field type designed to exclude specific fields from database operations
    and model interactions.

    This class inherits from `FieldFactory` to leverage its field creation capabilities
    and `type[None]` to signify that instances of this field should conceptually
    represent no value. It ensures that fields marked with `ExcludeField` are
    not included in JSON schemas, are treated as null, and cannot be set or retrieved
    after model initialization.

    Attributes:
        field_type (Any): Represents the type of the field. Set to `Any` as this
                          field acts as a placeholder for excluded types.
    """

    field_type: Any = Any

    def __new__(
        cls,
        **kwargs: Any,
    ) -> BaseFieldType:
        """
        Initializes a new instance of ExcludeField, configuring it for exclusion.

        This method overrides the default `__new__` to set specific properties
        that ensure the field is excluded from database and schema operations.
        It sets `exclude` to `True`, `null` to `True`, and `primary_key` to `False`
        before delegating to the `FieldFactory`'s `__new__` method.
        It also appends `SkipJsonSchema` to the field's metadata to prevent its
        inclusion in generated JSON schemas.

        Args:
            **kwargs (Any): Arbitrary keyword arguments passed during field creation.

        Returns:
            BaseFieldType: A configured instance of a field type that will be excluded.
        """
        # Set field properties to ensure exclusion
        kwargs["exclude"] = True
        kwargs["null"] = True
        kwargs["primary_key"] = False
        # Create the field using the parent FieldFactory
        field = super().__new__(cls, **kwargs)
        # Add metadata to skip JSON schema generation for this field
        field.metadata.append(SkipJsonSchema())

        return field

    @classmethod
    def clean(
        cls,
        obj: BaseFieldType,
        name: str,
        value: Any,
        for_query: bool = False,
        original_fn: Any = None,
    ) -> dict[str, Any]:
        """
        Removes any value from the input, effectively ignoring it.

        This class method is part of the field cleaning process. For `ExcludeField`,
        it ensures that any provided value is discarded by returning an empty
        dictionary. This is crucial for preventing excluded fields from being
        processed or stored, regardless of the input they receive.

        Args:
            obj (BaseFieldType): The field object itself.
            name (str): The name of the field.
            value (Any): The value associated with the field.
            for_query (bool): A flag indicating if the cleaning is for a query.
                              Defaults to `False`.
            original_fn (Any): The original function, if any, that was called.
                               Defaults to `None`.

        Returns:
            dict[str, Any]: An empty dictionary, signaling that the value
                            should be disregarded.
        """
        return {}

    @classmethod
    def to_model(
        cls,
        obj: BaseFieldType,
        name: str,
        value: Any,
        original_fn: Any = None,
    ) -> dict[str, Any]:
        """
        Handles the conversion of an excluded field to a model representation,
        raising an error if an attempt is made to set its value.

        This method is invoked during the process of converting data to a model
        instance. It checks the current phase of operation using `CURRENT_PHASE`.
        If the phase is "set", indicating an attempt to assign a value to the
        excluded field, a `ValueError` is raised. Otherwise, it returns an empty
        dictionary, effectively ignoring any incoming value.

        Args:
            obj (BaseFieldType): The field object itself.
            name (str): The name of the field.
            value (Any): The value to be converted.
            original_fn (Any): The original function, if any, that was called.
                               Defaults to `None`.

        Returns:
            dict[str, Any]: An empty dictionary, indicating no value should be
                            set on the model.

        Raises:
            ValueError: If an attempt is made to set a value for this excluded field.
        """
        # Get the current operational phase from context
        phase = CURRENT_PHASE.get()
        # If the phase is 'set', a value is being assigned to an excluded field
        if phase == "set":
            raise ValueError("field is excluded")
        return {}

    @classmethod
    def __get__(
        cls,
        obj: BaseFieldType,
        instance: BaseModelType,
        owner: Any = None,
        original_fn: Any = None,
    ) -> None:
        """
        Raises a ValueError when an attempt is made to access an excluded field.

        This descriptor method ensures that excluded fields cannot be read directly
        from a model instance. Any attempt to access such a field will result
        in a `ValueError`, reinforcing its excluded nature and preventing
        unintended data retrieval.

        Args:
            obj (BaseFieldType): The field object itself.
            instance (BaseModelType): The model instance from which the field
                                      is being accessed.
            owner (Any): The owner class of the field. Defaults to `None`.
            original_fn (Any): The original function, if any, that was called.
                               Defaults to `None`.

        Raises:
            ValueError: Always raises a ValueError as the field is excluded.
        """
        raise ValueError("field is excluded")
