from __future__ import annotations

import os
from dataclasses import dataclass, field
from importlib import import_module
from typing import TYPE_CHECKING, Any, Optional

from monkay import Monkay

from edgy.core.files.storage.handler import StorageHandler

if TYPE_CHECKING:
    from edgy.conf.global_settings import EdgySettings
    from edgy.core.connection import Registry


@dataclass
class Instance:
    registry: Registry
    app: Optional[Any] = None
    storages: StorageHandler = field(default_factory=StorageHandler)


def create_monkay(global_dict: dict, all_var: list[str]) -> Monkay[Instance, EdgySettings]:
    monkay: Monkay[Instance, EdgySettings] = Monkay(
        global_dict,
        with_extensions=True,
        with_instance=True,
        # must be at least an empty string to initialize the settings
        settings_path=os.environ.get(
            "EDGY_SETTINGS_MODULE", "edgy.conf.global_settings.EdgySettings"
        ),
        settings_extensions_name="extensions",
        settings_preloads_name="preloads",
        uncached_imports={"settings"},
        lazy_imports={
            "settings": lambda: monkay.settings,
            "EdgySettings": "edgy.conf.global_settings:EdgySettings",
            "fields": lambda: import_module("edgy.core.db.fields"),
            "files": lambda: import_module("edgy.core.files"),
            "Signal": "edgy.core.signals:Signal",
            "MultipleObjectsReturned": "edgy.exceptions:MultipleObjectsReturned",
            "ObjectNotFound": "edgy.exceptions:ObjectNotFound",
            "UniqueConstraint": "edgy.core.db.datastructures:UniqueConstraint",
            "Index": "edgy.core.db.datastructures:Index",
        },
        deprecated_lazy_imports={
            "Migrate": {
                "path": "edgy.cli.base:Migrate",
                "reason": "Use the monkay based system instead.",
                "new_attribute": "Instance",
            },
            "EdgyExtra": {
                "path": "edgy.cli.base:Migrate",
                "reason": "Use the monkay based system instead.",
                "new_attribute": "Instance",
            },
        },
        skip_all_update=True,
    )
    for name in [
        "CASCADE",
        "RESTRICT",
        "DO_NOTHING",
        "SET_NULL",
        "SET_DEFAULT",
        "PROTECT",
        "NEW_M2M_NAMING",
        "OLD_M2M_NAMING",
        "ConditionalRedirect",
    ]:
        monkay.add_lazy_import(name, f"edgy.core.db.constants.{name}")

    for name in ["Database", "DatabaseURL", "Registry"]:
        monkay.add_lazy_import(name, f"edgy.core.connection.{name}")

    for name in ["Prefetch", "Q", "QuerySet", "and_", "not_", "or_"]:
        monkay.add_lazy_import(name, f"edgy.core.db.querysets.{name}")

    for name in ["Manager", "Model", "ModelRef", "RedirectManager", "ReflectModel", "StrictModel"]:
        monkay.add_lazy_import(name, f"edgy.core.db.models.{name}")

    for name in all_var:
        if name.endswith("Field") or name in {
            "OneToOne",
            "ManyToMany",
            "ForeignKey",
            "RefForeignKey",
        }:
            monkay.add_lazy_import(name, f"edgy.core.db.fields.{name}")
    return monkay
