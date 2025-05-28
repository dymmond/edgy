from __future__ import annotations

from typing import TYPE_CHECKING

from typing_extensions import TypedDict

if TYPE_CHECKING:
    from edgy.core.db.models import Model


class ConfigMarshall(TypedDict, total=False):
    """A TypedDict for configuring Marshall behaviour."""

    model: type[Model] | str
    """The model from there the marshall will read from."""

    fields: list[str] | None = None
    """A list of fields to be serialized"""

    exclude: list[str] | None = None
    """A list of fields to be excluded from the serialization."""
