from __future__ import annotations

import os
from dataclasses import dataclass, field
from importlib import import_module
from typing import TYPE_CHECKING, Any

from monkay import Monkay

from edgy.core.files.storage.handler import StorageHandler

if TYPE_CHECKING:
    from edgy.conf.global_settings import EdgySettings
    from edgy.core.connection import Registry


@dataclass
class Instance:
    """
    Represents an instance of the Edgy application, holding references to the registry,
    the application instance itself, and the storage handler.
    """

    registry: Registry
    app: Any | None = None
    storages: StorageHandler = field(default_factory=StorageHandler)


def create_monkay(global_dict: dict, all_var: list[str]) -> Monkay[Instance, EdgySettings]:
    """
    Initializes and configures a Monkay instance for Edgy.

    This function sets up the Monkay dependency injection container with various
    lazy imports, settings, and extensions required for the Edgy framework
    to function correctly. It also handles deprecated lazy imports and
    populates Monkay with essential Edgy components.

    Args:
        global_dict (dict): The global dictionary from which Monkay will resolve
            dependencies. This typically includes '__name__', '__file__', etc.
        all_var (list[str]): A list of all variables, specifically used to
            dynamically add field-related lazy imports.

    Returns:
        Monkay[Instance, "EdgySettings"]: A fully configured Monkay instance
        ready for use with Edgy.
    """
    # Initialize Monkay with core configurations
    monkay: Monkay[Instance, EdgySettings] = Monkay(
        global_dict,
        with_extensions=True,  # Enables Monkay extensions
        with_instance=True,  # Enables instance management
        # Dynamically sets the path to the Edgy settings module.
        # It first checks the EDGY_SETTINGS_MODULE environment variable,
        # then defaults to 'edgy.conf.global_settings.EdgySettings',
        # falling back to an empty string if neither is found.
        settings_path=lambda: os.environ.get(
            "EDGY_SETTINGS_MODULE", "edgy.conf.global_settings.EdgySettings"
        )
        or "",
        settings_extensions_name="extensions",  # Name for settings extensions
        settings_preloads_name="preloads",  # Name for settings preloads
        uncached_imports={"settings"},  # Imports that should not be cached
        lazy_imports={
            "settings": lambda: monkay.settings,  # Lazy import for application settings
            "EdgySettings": "edgy.conf.global_settings:EdgySettings",  # Edgy settings class
            "marshalls": lambda: import_module(
                "edgy.core.marshalls"
            ),  # Lazy import for marshalling utilities
            "fields": lambda: import_module(
                "edgy.core.db.fields"
            ),  # Lazy import for database fields
            "files": lambda: import_module("edgy.core.files"),  # Lazy import for file handling
            "Signal": "edgy.core.signals:Signal",  # Signal class
            "MultipleObjectsReturned": "edgy.exceptions:MultipleObjectsReturned",  # Exception for multiple objects found
            "ObjectNotFound": "edgy.exceptions:ObjectNotFound",  # Exception for object not found
            "UniqueConstraint": "edgy.core.db.datastructures:UniqueConstraint",  # UniqueConstraint class
            "Index": "edgy.core.db.datastructures:Index",  # Index class
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
        skip_all_update=True,  # Skips all updates during Monkay initialization
    )
    # Add lazy imports for database constants
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

    # Add lazy imports for connection-related classes
    for name in ["Database", "DatabaseURL", "Registry"]:
        monkay.add_lazy_import(name, f"edgy.core.connection.{name}")

    # Add lazy imports for queryset and query-related classes
    for name in ["Prefetch", "Q", "QuerySet", "and_", "not_", "or_"]:
        monkay.add_lazy_import(name, f"edgy.core.db.querysets.{name}")

    # Add lazy imports for model-related classes
    for name in ["Manager", "Model", "ModelRef", "RedirectManager", "ReflectModel", "StrictModel"]:
        monkay.add_lazy_import(name, f"edgy.core.db.models.{name}")

    # Dynamically add lazy imports for field types
    for name in all_var:
        if name.endswith("Field") or name in {
            "OneToOne",
            "ManyToMany",
            "ForeignKey",
            "RefForeignKey",
        }:
            monkay.add_lazy_import(name, f"edgy.core.db.fields.{name}")
    return monkay
