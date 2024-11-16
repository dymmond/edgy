from __future__ import annotations

__version__ = "0.23.0"
import os
from importlib import import_module
from typing import TYPE_CHECKING, Any, NamedTuple, Optional

from monkay import Monkay

from edgy.conf.global_settings import EdgySettings
from edgy.core.connection import Database, DatabaseURL, Registry
from edgy.core.db.models import (
    Manager,
    Model,
    ModelRef,
    RedirectManager,
    ReflectModel,
    StrictModel,
)
from edgy.core.db.querysets import Prefetch, Q, QuerySet, and_, not_, or_
from edgy.core.utils.sync import run_sync

if TYPE_CHECKING:
    from .core.db.datastructures import Index, UniqueConstraint
    from .core.signals import Signal
    from .exceptions import MultipleObjectsReturned, ObjectNotFound


class Instance(NamedTuple):
    registry: Registry
    app: Optional[Any] = None


__all__ = [
    "Instance",
    "get_migration_prepared_registry",
    "monkay",
    "and_",
    "not_",
    "or_",
    "Q",
    "EdgyExtra",
    "EdgySettings",
    "files",
    "Migrate",
    "Prefetch",
    "QuerySet",
    "Signal",
    "settings",
    "run_sync",
    # index and constraint
    "Index",
    "UniqueConstraint",
    # some exceptions
    "MultipleObjectsReturned",
    "ObjectNotFound",
    # constants
    "CASCADE",
    "RESTRICT",
    "DO_NOTHING",
    "SET_NULL",
    "SET_DEFAULT",
    "PROTECT",
    "ConditionalRedirect",
    # models
    "ReflectModel",
    "StrictModel",
    "Model",
    "ModelRef",
    "Manager",
    "RedirectManager",
    # fields
    "fields",
    "BigIntegerField",
    "BinaryField",
    "BooleanField",
    "CharField",
    "ChoiceField",
    "ComputedField",
    "CompositeField",
    "DateField",
    "DateTimeField",
    "DurationField",
    "DecimalField",
    "EmailField",
    "ExcludeField",
    "FloatField",
    "ImageField",
    "FileField",
    "ForeignKey",
    "OneToOne",
    "OneToOneField",
    "PasswordField",
    "PlaceholderField",
    "SmallIntegerField",
    "TextField",
    "TimeField",
    "URLField",
    "UUIDField",
    "ManyToMany",
    "ManyToManyField",
    "IntegerField",
    "JSONField",
    "RefForeignKey",
    "IPAddressField",
    # base connection
    "Database",
    "DatabaseURL",
    "Registry",
]

monkay: Monkay[Instance, EdgySettings] = Monkay(
    globals(),
    with_extensions=True,
    with_instance=True,
    # must be at least an empty string to initialize the settings
    settings_path=os.environ.get("EDGY_SETTINGS_MODULE", "edgy.conf.global_settings.EdgySettings"),
    settings_extensions_name="extensions",
    settings_preloads_name="preloads",
    uncached_imports={"settings"},
    lazy_imports={
        "settings": lambda: monkay.settings,
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
    "ConditionalRedirect",
]:
    monkay.add_lazy_import(name, f"edgy.core.db.constants.{name}")

for name in __all__:
    if name.endswith("Field") or name in {
        "OneToOne",
        "ManyToMany",
        "ForeignKey",
        "RefForeignKey",
    }:
        monkay.add_lazy_import(name, f"edgy.core.db.fields.{name}")

del name


def get_migration_prepared_registry() -> Registry:
    """Get registry with applied restrictions, usable for migrations."""
    instance = monkay.instance
    assert instance is not None
    registry = instance.registry
    assert registry is not None
    registry.refresh_metadata(
        multi_schema=monkay.settings.multi_schema,
        ignore_schema_pattern=monkay.settings.ignore_schema_pattern,
    )
    return registry
