from __future__ import annotations

__version__ = "0.22.0"
import os
from importlib import import_module
from typing import TYPE_CHECKING

from monkay import Monkay

from .core.utils.sync import run_sync

if TYPE_CHECKING:
    from .conf.global_settings import EdgySettings
    from .core.connection import Database, DatabaseURL, Registry
    from .core.db.datastructures import Index, UniqueConstraint
    from .core.db.models import (
        Manager,
        Model,
        ModelRef,
        RedirectManager,
        ReflectModel,
        StrictModel,
    )
    from .core.db.querysets import Prefetch, Q, QuerySet, and_, not_, or_
    from .core.signals import Signal
    from .exceptions import MultipleObjectsReturned, ObjectNotFound

__all__ = [
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

monkay: Monkay[Registry, EdgySettings] = Monkay(
    globals(),
    with_extensions=True,
    with_instance=True,
    settings_path=os.environ.get("EDGY_SETTINGS_MODULE", "edgy.conf.global_settings.EdgySettings"),
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
    },
    deprecated_lazy_imports={
        "Migrate": {
            "path": "edgy.cli.base:Migrate",
            "reason": "Use the monkay based system instead.",
        },
        "EdgyExtra": {
            "path": "edgy.core.extras:EdgyExtra",
            "reason": "Use the monkay based system instead.",
        },
    },
    skip_all_update=True,
)

for name in ["Manager", "Model", "ModelRef", "RedirectManager", "ReflectModel", "StrictModel"]:
    monkay.add_lazy_import(name, f"edgy.core.db.models.{name}")
for name in ["Database", "DatabaseURL", "Registry"]:
    monkay.add_lazy_import(name, f"edgy.core.connection.{name}")
for name in ["Prefetch", "Q", "QuerySet", "and_", "not_", "or_"]:
    monkay.add_lazy_import(name, f"edgy.core.db.querysets.{name}")
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
