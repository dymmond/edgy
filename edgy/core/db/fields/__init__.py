from typing import TYPE_CHECKING

from monkay import Monkay

from .base import BaseField
from .types import BaseFieldType

if TYPE_CHECKING:
    from .composite_field import CompositeField
    from .core import (
        BigIntegerField,
        BinaryField,
        BooleanField,
        CharField,
        ChoiceField,
        ComputedField,
        DateField,
        DateTimeField,
        DecimalField,
        DurationField,
        EmailField,
        FloatField,
        IntegerField,
        IPAddressField,
        JSONField,
        PasswordField,
        PlaceholderField,
        SmallIntegerField,
        TextField,
        TimeField,
        URLField,
        UUIDField,
    )
    from .exclude_field import ExcludeField
    from .file_field import FileField
    from .foreign_keys import ForeignKey
    from .image_field import ImageField
    from .many_to_many import ManyToMany, ManyToManyField
    from .one_to_one_keys import OneToOne, OneToOneField
    from .ref_foreign_key import RefForeignKey

__all__ = [
    "BaseField",
    "BaseFieldType",
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
    "FileField",
    "ImageField",
    "ForeignKey",
    "IntegerField",
    "IPAddressField",
    "JSONField",
    "RefForeignKey",
    "ManyToMany",
    "ManyToManyField",
    "OneToOne",
    "OneToOneField",
    "PasswordField",
    "PlaceholderField",
    "SmallIntegerField",
    "TextField",
    "TimeField",
    "URLField",
    "UUIDField",
    "PGArrayField",
]

Monkay(
    globals(),
    lazy_imports={
        "BigIntegerField": ".core.BigIntegerField",
        "BinaryField": ".core.BinaryField",
        "BooleanField": ".core.BooleanField",
        "CharField": ".core.CharField",
        "ChoiceField": ".core.ChoiceField",
        "ComputedField": ".computed_field.ComputedField",
        "CompositeField": ".composite_field.CompositeField",
        "DateField": ".core.DateField",
        "DateTimeField": ".core.DateTimeField",
        "DurationField": ".core.DurationField",
        "DecimalField": ".core.DecimalField",
        "EmailField": ".core.EmailField",
        "ExcludeField": ".exclude_field.ExcludeField",
        "FloatField": ".core.FloatField",
        "FileField": ".file_field.FileField",
        "ImageField": ".image_field.ImageField",
        "ForeignKey": ".foreign_keys.ForeignKey",
        "IntegerField": ".core.IntegerField",
        "IPAddressField": ".core.IPAddressField",
        "JSONField": ".core.JSONField",
        "RefForeignKey": ".ref_foreign_key.RefForeignKey",
        "ManyToMany": ".many_to_many.ManyToMany",
        "ManyToManyField": ".many_to_many.ManyToMany",
        "OneToOne": ".one_to_one_keys.OneToOne",
        "OneToOneField": ".one_to_one_keys.OneToOne",
        "PasswordField": ".core.PasswordField",
        "PlaceholderField": ".place_holder_field.PlaceholderField",
        "SmallIntegerField": ".core.SmallIntegerField",
        "TextField": ".core.TextField",
        "TimeField": ".core.TimeField",
        "URLField": ".core.URLField",
        "UUIDField": ".core.UUIDField",
        "PGArrayField": ".postgres.PGArrayField",
    },
    deprecated_lazy_imports={
        "AutoNowMixin": {
            "path": ".mixins.AutoNowMixin",
            "reason": "We export mixins now from edgy.core.db.fields.mixins.",
            "new_attribute": "edgy.core.db.fields.mixins.AutoNowMixin",
        }
    },
    skip_all_update=True,
)
