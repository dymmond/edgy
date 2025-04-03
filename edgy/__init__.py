from __future__ import annotations

__version__ = "0.30.0"
from typing import TYPE_CHECKING

from ._monkay import Instance, create_monkay
from .core.utils.sync import run_sync

if TYPE_CHECKING:
    from .conf.global_settings import EdgySettings
    from .core import files
    from .core.connection import Database, DatabaseURL, Registry
    from .core.db import fields
    from .core.db.constants import (
        CASCADE,
        DO_NOTHING,
        NEW_M2M_NAMING,
        OLD_M2M_NAMING,
        PROTECT,
        RESTRICT,
        SET_DEFAULT,
        SET_NULL,
        ConditionalRedirect,
    )
    from .core.db.datastructures import Index, UniqueConstraint

    # for type checking import all fields
    from .core.db.fields import (
        BigIntegerField,
        BinaryField,
        BooleanField,
        CharField,
        ChoiceField,
        CompositeField,
        ComputedField,
        DateField,
        DateTimeField,
        DecimalField,
        DurationField,
        EmailField,
        ExcludeField,
        FileField,
        FloatField,
        ForeignKey,
        ImageField,
        IntegerField,
        IPAddressField,
        JSONField,
        ManyToMany,
        ManyToManyField,
        OneToOne,
        OneToOneField,
        PasswordField,
        PGArrayField,
        PlaceholderField,
        RefForeignKey,
        SmallIntegerField,
        TextField,
        TimeField,
        URLField,
        UUIDField,
    )
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
    "NEW_M2M_NAMING",
    "OLD_M2M_NAMING",
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
    "PGArrayField",
    # base connection
    "Database",
    "DatabaseURL",
    "Registry",
]
monkay = create_monkay(globals(), __all__)

del create_monkay


def get_migration_prepared_registry(registry: Registry | None = None) -> Registry:
    """Get registry with applied restrictions, usable for migrations."""
    # ensure settings are ready
    monkay.evaluate_settings(ignore_import_errors=False)
    if registry is None:
        instance = monkay.instance
        assert instance is not None
        registry = instance.registry
    assert registry is not None
    registry.refresh_metadata(
        multi_schema=monkay.settings.multi_schema,
        ignore_schema_pattern=monkay.settings.ignore_schema_pattern,
    )
    return registry
