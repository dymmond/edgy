from __future__ import annotations

from typing import TypedDict

from edgy.core.db import models  # fixes model not defined errors in pydantic


class ConfigMarshall(TypedDict, total=False):
    """A TypedDict for configuring Marshall behaviour."""

    model: type[models.Model] | str
    """The model from there the marshall will read from."""

    fields: list[str] | None = None
    """A list of fields to be serialized"""

    exclude: list[str] | None = None
    """A list of fields to be excluded from the serialization."""
