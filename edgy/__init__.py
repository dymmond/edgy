from __future__ import annotations

__version__ = "0.23.1"
from typing import TYPE_CHECKING

from ._monkay import Instance, create_monkay
from .core.utils.sync import run_sync

if TYPE_CHECKING:
    from .conf.global_settings import EdgySettings
    from .core import files
    from .core.connection import Database, DatabaseURL, Registry
    from .core.db import fields
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
monkay = create_monkay(globals(), __all__)

del create_monkay


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
