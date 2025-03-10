from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from monkay import Monkay

from .handler import StorageHandler

if TYPE_CHECKING:
    from edgy import EdgySettings, Instance

    from .base import Storage
storages: StorageHandler


_fallback_storage = StorageHandler()


@lru_cache
def _get_monkay() -> Monkay[Instance, EdgySettings]:
    from edgy import monkay

    return monkay


def _get_storages() -> StorageHandler:
    instance = _get_monkay().instance
    return _fallback_storage if instance is None else instance.storages


Monkay(
    globals(),
    lazy_imports={
        "Storage": ".base.Storage",
        "storages": _get_storages,
    },
    uncached_imports={"storages"},
)

__all__ = ["Storage", "StorageHandler", "storages"]
