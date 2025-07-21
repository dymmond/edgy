from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel


class ModelRef(BaseModel):
    """
    Represents a reference to a model with a specified related name.

    This class is typically used internally within Edgy to manage relationships
    between models, especially when defining foreign keys or many-to-many relationships,
    where a `related_name` is necessary for reverse lookups.

    Attributes:
        __related_name__ (ClassVar[str]): A class variable that defines the name
                                         to use for the reverse relation from the
                                         related model back to this model. This is
                                         crucial for accessing related objects in queries.
    """

    __related_name__: ClassVar[str]
