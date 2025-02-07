from typing import TYPE_CHECKING

from monkay import Monkay

if TYPE_CHECKING:
    from .client import DatabaseTestClient
    from .factory import (
        FactoryField,
        ListSubFactory,
        ModelFactory,
        ModelFactoryContext,
        SubFactory,
    )

__all__ = [
    "DatabaseTestClient",
    "ModelFactory",
    "SubFactory",
    "ListSubFactory",
    "FactoryField",
    "ModelFactoryContext",
]


Monkay(
    globals(),
    lazy_imports={
        "ModelFactory": ".factory.ModelFactory",
        "ModelFactoryContext": ".factory.ModelFactoryContext",
        "SubFactory": ".factory.SubFactory",
        "ListSubFactory": ".factory.ListSubFactory",
        "FactoryField": ".factory.FactoryField",
        "DatabaseTestClient": ".client.DatabaseTestClient",
    },
)
del Monkay
