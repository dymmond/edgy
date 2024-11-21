from __future__ import annotations

from typing import TYPE_CHECKING, Union

from typing_extensions import TypedDict

if TYPE_CHECKING:
    from edgy.core.db.models import Model


class ConfigMarshall(TypedDict, total=False):
    """A TypedDict for configuring Marshall behaviour."""

    model: Union[type[Model], str]
    """The model from there the marshall will read from."""

    fields: Union[list[str], None]
    """A list of fields to be serialized"""

    exclude: Union[list[str], None]
    """A list of fields to be excluded from the serialization."""
