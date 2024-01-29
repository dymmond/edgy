"""Configuration for Pydantic models."""

from __future__ import annotations as _annotations

from typing_extensions import TypedDict


class ModelConfig(TypedDict, total=False):
    """
    A TypedDict for configuring Model behaviour.
    """

    strict: bool
    """
    Weather the model should be strict in the creation or not.
    """
    populate_by_alias: bool
    """
    Whether an aliased field may be populated by its name as given by the model
    attribute, as well as the alias. Defaults to `False`.
    """
