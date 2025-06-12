from typing import TYPE_CHECKING

from monkay import Monkay

if TYPE_CHECKING:
    from .base import Marshall
    from .config import ConfigMarshall
    from .fields import MarshallField, MarshallMethodField

__all__ = ["ConfigMarshall", "Marshall", "MarshallField", "MarshallMethodField"]

Monkay(
    globals(),
    lazy_imports={
        "Marshall": ".base.Marshall",
        "ConfigMarshall": ".config.ConfigMarshall",
        "MarshallField": ".fields.MarshallField",
        "MarshallMethodField": ".fields.MarshallMethodField",
    },
)
