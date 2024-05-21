from typing import TYPE_CHECKING, List, Union

from typing_extensions import TypedDict

if TYPE_CHECKING:
    from edgy import Model


class ConfigMarshall(TypedDict, total=False):
    """A TypedDict for configuring Marshall behaviour."""

    model: Union["Model", str]
    """The model from there the marshall will read from."""

    fields: Union[List[str], None]
    """A list of fields to be serialized"""

    exclude: Union[List[str], None]
    """A list of fields to be excluded from the serialization."""
