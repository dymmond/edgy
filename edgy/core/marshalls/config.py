from typing import TYPE_CHECKING, Union

from typing_extensions import TypedDict

if TYPE_CHECKING:
    from edgy.core.db.models import BaseModelType


class ConfigMarshall(TypedDict, total=False):
    """A TypedDict for configuring Marshall behaviour."""

    model: Union["BaseModelType", str]
    """The model from there the marshall will read from."""

    fields: Union[list[str], None]
    """A list of fields to be serialized"""

    exclude: Union[list[str], None]
    """A list of fields to be excluded from the serialization."""
