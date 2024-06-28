from typing import TYPE_CHECKING, Any, TypeVar, Union

from edgy.core.db.fields.foreign_keys import ForeignKey
from edgy.core.terminal import Print

if TYPE_CHECKING:
    from edgy import Model
    from edgy.core.db.fields.base import BaseField

T = TypeVar("T", bound="Model")

terminal = Print()

class OneToOneField(ForeignKey):
    """
    Representation of a one to one field.
    """

    def __new__(  # type: ignore
        cls,
        to: Union["Model", str],
        **kwargs: Any,
    ) -> "BaseField":
        for argument in ["index", "unique"]:
            if argument in kwargs:
                terminal.write_warning(f"Declaring {argument} on a OneToOneField has no effect.")
        kwargs["unique"] = True

        return super().__new__(cls, to=to, **kwargs)

OneToOne = OneToOneField
