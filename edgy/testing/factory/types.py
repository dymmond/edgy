from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Protocol, TypedDict

if TYPE_CHECKING:
    from faker import Faker

    from edgy.core.db.fields.types import BaseFieldType

    from .fields import FactoryField


class _ModelFactoryContext(TypedDict):
    faker: Faker
    exclude_autoincrement: bool
    depth: int
    callcounts: dict[int, int]


if TYPE_CHECKING:

    class ModelFactoryContext(Faker, _ModelFactoryContext, Protocol):
        pass
else:
    ModelFactoryContext = _ModelFactoryContext


FactoryParameterCallback = Callable[
    [
        "FactoryField",
        ModelFactoryContext,
        str,
    ],
    Any,
]
FactoryParameters = dict[str, Any | FactoryParameterCallback]
FactoryCallback = Callable[["FactoryField", ModelFactoryContext, dict[str, Any]], Any]
FieldFactoryCallback = str | FactoryCallback
FactoryFieldType = str | "BaseFieldType" | type["BaseFieldType"]
