from __future__ import annotations

from typing import TYPE_CHECKING, Any

from edgy.core.db.fields.foreign_keys import ForeignKey
from edgy.core.terminal import Print

if TYPE_CHECKING:
    from edgy.core.db.fields.types import BaseFieldType
    from edgy.core.db.models.types import BaseModelType


# Initialize a terminal printer for warnings.
terminal = Print()


class OneToOneField(ForeignKey):
    """
    Representation of a one-to-one field.

    This field is a specialized `ForeignKey` that enforces a unique constraint
    on the foreign key column, effectively creating a one-to-one relationship.
    It issues warnings if `index` or `unique` arguments are explicitly provided
    during initialization, as `unique` is automatically set to `True` for
    one-to-one relationships, rendering `index` redundant.
    """

    def __new__(
        cls,
        to: type[BaseModelType] | str,
        **kwargs: Any,
    ) -> BaseFieldType:
        """
        Creates a new `OneToOneField` instance.

        This method overrides the `__new__` method of `ForeignKey` to ensure
        that the `unique` constraint is always applied for one-to-one relationships.
        It also provides warnings if redundant arguments like `index` or `unique`
        are passed explicitly, as they are implicitly handled by the one-to-one nature.

        Args:
            to (type[BaseModelType] | str): The target model class or its string name
                                          to which this one-to-one field points.
            **kwargs (Any): Arbitrary keyword arguments passed to the `ForeignKey` constructor.

        Returns:
            BaseFieldType: The constructed `OneToOneField` instance.
        """
        # Iterate over arguments that are implicitly handled by OneToOneField.
        # If they are explicitly provided, issue a warning.
        for argument in ["index", "unique"]:
            if argument in kwargs:
                terminal.write_warning(f"Declaring {argument} on a OneToOneField has no effect.")
        # Force the 'unique' constraint to be True for all OneToOneFields.
        # This is the core characteristic that distinguishes it from a regular ForeignKey.
        kwargs["unique"] = True

        # Call the parent class's __new__ method to create the actual field instance.
        return super().__new__(cls, to=to, **kwargs)


# Alias OneToOneField for convenience, following common Edgy naming conventions.
OneToOne = OneToOneField
