from __future__ import annotations

from typing import TYPE_CHECKING, Any, Union

from edgy.core.db.fields.foreign_keys import ForeignKey
from edgy.core.terminal import Print

if TYPE_CHECKING:
    from edgy.core.db.fields.types import BaseFieldType
    from edgy.core.db.models.types import BaseModelType


terminal = Print()


class OneToOneField(ForeignKey):
    """
    Representation of a one to one field.
    """

    def __new__(  # type: ignore
        cls,
        to: Union[type[BaseModelType], str],
        **kwargs: Any,
    ) -> BaseFieldType:
        for argument in ["index", "unique"]:
            if argument in kwargs:
                terminal.write_warning(f"Declaring {argument} on a OneToOneField has no effect.")
        kwargs["unique"] = True

        return super().__new__(cls, to=to, **kwargs)


OneToOne = OneToOneField
