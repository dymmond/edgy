from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Union

if TYPE_CHECKING:
    from faker import Faker

    from edgy.core.db.fields.types import BaseFieldType

    from .fields import FactoryField


FactoryParameterCallback = Callable[
    [
        "FactoryField",
        "Faker",
        str,
    ],
    Any,
]
FactoryParameters = dict[str, Union[Any, FactoryParameterCallback]]
FactoryCallback = Callable[["FactoryField", "Faker", dict[str, Any]], Any]
FieldFactoryCallback = Union[FactoryCallback, str]
FactoryFieldType = Union[str, "BaseFieldType", type["BaseFieldType"]]
