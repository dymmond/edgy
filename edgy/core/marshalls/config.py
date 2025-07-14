from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from edgy.core.db.models.model import Model


class ConfigMarshall(TypedDict, total=False):
    """A TypedDict for configuring Marshall behaviour."""

    model: type[Model] | str
    """The model from there the marshall will read from."""

    fields: list[str] | None = None
    """A list of fields to be serialized"""

    exclude: list[str] | None = None
    """A list of fields to be excluded from the serialization."""

    primary_key_read_only: bool = False
    """Make primary_key fields read-only."""

    exclude_autoincrement: bool = False
    """Post-filter autoincrement fields."""

    # used for a workaround for the missing of a readOnly flag in the jsonSchema when read_only is true.
    exclude_read_only: bool = False
    """Post-filter read-only fields. Removes also read-only made primary_keys."""
