from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from faker import Faker

    from edgy.core.db.fields.types import BaseFieldType

    from .fields import FactoryField


FactoryParameters = dict[str, Any]
FactoryCallback = Callable[[FactoryField, Faker, FactoryParameters], Any]
FactoryFieldType = str | BaseFieldType | type[BaseFieldType]
