from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Protocol, TypedDict, Union

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
FactoryParameters = dict[str, Union[Any, FactoryParameterCallback]]
FactoryCallback = Callable[["FactoryField", ModelFactoryContext, dict[str, Any]], Any]
FieldFactoryCallback = Union[FactoryCallback, str]
FactoryFieldType = Union[str, "BaseFieldType", type["BaseFieldType"]]
