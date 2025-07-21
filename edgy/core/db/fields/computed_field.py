from __future__ import annotations

from collections.abc import Callable
from functools import cached_property
from typing import TYPE_CHECKING, Any, cast

from edgy.core.db.fields.base import BaseField
from edgy.core.db.fields.types import BaseFieldType

if TYPE_CHECKING:
    from edgy.core.db.models.types import BaseModelType


class ComputedField(BaseField):
    """
    Represents a computed field in an Edgy model.

    A computed field's value is not stored directly in the database but is
    derived from other fields or logic using a `getter` function. It can
    optionally have a `setter` function to define how values are processed
    when assigned, though these assignments do not persist to the database
    unless handled by the setter's logic.

    Attributes:
        getter: A callable or string name of a method on the owner model
                that retrieves the computed value.
        setter: An optional callable or string name of a method on the owner
                model that sets the computed value. If None, setting has no effect.
        fallback_getter: An optional callable to use as a getter if the primary
                         `getter` (especially when a string name) is not found
                         on the owner.
    """

    def __init__(
        self,
        getter: Callable[[BaseFieldType, BaseModelType, type[BaseModelType] | None], Any] | str,
        setter: Callable[[BaseFieldType, BaseModelType, Any], None] | str | None = None,
        fallback_getter: (
            Callable[[BaseFieldType, BaseModelType, type[BaseModelType] | None], Any] | None
        ) = None,
        **kwargs: Any,
    ) -> None:
        """
        Initializes a `ComputedField` instance.

        Sets default field properties like `exclude`, `null`, and `primary_key`
        to ensure it behaves as a non-persisted, computed attribute.

        Args:
            getter: The function or method name responsible for computing the field's value.
            setter: The optional function or method name responsible for handling
                    assignments to the field.
            fallback_getter: An alternative getter to use if the primary getter is not found.
            **kwargs: Additional keyword arguments passed to the `BaseField` constructor.
        """
        # Exclude computed fields from default Pydantic serialization.
        kwargs.setdefault("exclude", True)
        # Computed fields are not nullable in the database sense, but for Pydantic
        # they should allow None.
        kwargs["null"] = True
        # Computed fields are never primary keys.
        kwargs["primary_key"] = False
        # Set the field type and annotation to Any as the computed value can be anything.
        kwargs["field_type"] = kwargs["annotation"] = Any

        # Store the getter, fallback_getter, and setter.
        self.getter = getter
        self.fallback_getter = fallback_getter
        self.setter = setter

        # Call the parent BaseField constructor with remaining kwargs.
        super().__init__(**kwargs)

    @cached_property
    def compute_getter(
        self,
    ) -> Callable[[BaseFieldType, BaseModelType, type[BaseModelType] | None], Any]:
        """
        Resolves and caches the actual getter callable for the computed field.

        If `self.getter` is a string, it attempts to find a method with that
        name on the `owner` model. If not found, it tries `fallback_getter`.

        Returns:
            The callable function that computes the field's value.

        Raises:
            ValueError: If no getter (neither primary nor fallback) can be found.
        """
        fn: Callable[[BaseFieldType, BaseModelType, type[BaseModelType] | None], Any] | None
        # If the getter is a string, try to get the method from the owner.
        if isinstance(self.getter, str):
            fn = cast(
                Callable[[BaseFieldType, "BaseModelType", type["BaseModelType"] | None], Any]
                | None,
                getattr(self.owner, self.getter, None),
            )
        else:
            # If the getter is already a callable, use it directly.
            fn = self.getter

        # If the primary getter is not found, try the fallback getter.
        if fn is None and self.fallback_getter is not None:
            fn = self.fallback_getter

        # If no getter is found, raise an error.
        if fn is None:
            raise ValueError(f"No getter found for attribute: {self.getter}.")
        return fn

    @cached_property
    def compute_setter(self) -> Callable[[BaseFieldType, BaseModelType, Any], None]:
        """
        Resolves and caches the actual setter callable for the computed field.

        If `self.setter` is a string, it attempts to find a method with that
        name on the `owner` model. If no setter is provided or found, it returns
        a no-op function.

        Returns:
            The callable function that handles setting the field's value,
            or a no-op function if no setter is defined.
        """
        fn: Callable[[BaseFieldType, BaseModelType, Any], None] | None
        # If the setter is a string, try to get the method from the owner.
        if isinstance(self.setter, str):
            fn = cast(
                Callable[[BaseFieldType, "BaseModelType", Any], None] | None,
                getattr(self.owner, self.setter, None),
            )
        else:
            # If the setter is already a callable, use it directly.
            fn = self.setter

        # If no setter is found, return a lambda that does nothing.
        if fn is None:
            return lambda instance, name, value: None
        return fn

    def to_model(
        self,
        field_name: str,
        value: Any,
    ) -> dict[str, Any]:
        """
        Converts the value of the computed field for model instantiation.

        Computed fields are typically derived, not directly loaded from
        the database, so this method always returns an empty dictionary,
        indicating no direct database mapping for this field.

        Args:
            field_name: The name of the field.
            value: The value (ignored for computed fields).

        Returns:
            An empty dictionary.
        """
        return {}

    def clean(
        self,
        name: str,
        value: Any,
        for_query: bool = False,
    ) -> dict[str, Any]:
        """
        Cleans and prepares the value of the computed field.

        Computed fields are not stored in the database, so this method
        always returns an empty dictionary as there is nothing to clean
        or prepare for database interaction.

        Args:
            name: The name of the field.
            value: The value (ignored for computed fields).
            for_query: A boolean indicating if the cleaning is for a query context.

        Returns:
            An empty dictionary.
        """
        return {}

    def __get__(self, instance: BaseModelType, owner: Any = None) -> Any:
        """
        Descriptor method to retrieve the computed field's value.

        This method is called when accessing the field on a model instance.
        It delegates the actual computation to the `compute_getter` callable.

        Args:
            instance: The model instance from which to get the value.
            owner: The owner class (not typically used for instance access).

        Returns:
            The computed value of the field.
        """
        return self.compute_getter(self, instance, owner)

    def __set__(self, instance: BaseModelType, value: Any) -> None:
        """
        Descriptor method to set the computed field's value.

        This method is called when assigning a value to the field on a model instance.
        It delegates the handling of the assignment to the `compute_setter` callable.
        Note that setting a computed field does not typically persist to the
        database unless the setter's logic explicitly handles it.

        Args:
            instance: The model instance on which to set the value.
            value: The value to be set.
        """
        self.compute_setter(self, instance, value)
