import copy
import inspect
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    List,
    Optional,
    Sequence,
    Set,
    Type,
    TypeVar,
    Union,
    cast,
)

import sqlalchemy

from edgy.conf import settings
from edgy.core.connection.database import Database
from edgy.core.connection.registry import Registry
from edgy.core.db import fields, models
from edgy.core.db.datastructures import Index, UniqueConstraint
from edgy.core.db.fields.base import BaseField
from edgy.core.db.models.managers import Manager
from edgy.core.db.relationships.related_field import RelatedField
from edgy.core.db.relationships.relation import Relation
from edgy.exceptions import ForeignKeyBadConfigured, ImproperlyConfigured

if TYPE_CHECKING:
    from edgy.core.db.models import Model, ReflectModel


class MetaInfo:
    __slots__ = (
        "pk",
        "pk_attribute",
        "abstract",
        "fields",
        "fields_mapping",
        "registry",
        "tablename",
        "unique_together",
        "indexes",
        "foreign_key_fields",
        "parents",
        "one_to_one_fields",
        "many_to_many_fields",
        "manager",
        "model",
        "reflect",
        "managers",
        "is_multi",
        "multi_related",
        "related_names",
    )

    def __init__(self, meta: Any = None) -> None:
        self.pk: Optional[BaseField] = None
        self.pk_attribute: Union[BaseField, str] = getattr(meta, "pk_attribute", "")
        self.abstract: bool = getattr(meta, "abstract", False)
        self.fields: Set = set()
        self.fields_mapping: Dict[str, BaseField] = {}
        self.registry: Optional[Type[Registry]] = getattr(meta, "registry", None)
        self.tablename: Optional[str] = getattr(meta, "tablename", None)
        self.parents: Any = getattr(meta, "parents", None) or []
        self.one_to_one_fields: Set[str] = set()
        self.many_to_many_fields: Set[str] = set()
        self.foreign_key_fields: Set[str] = set()
        self.model: Optional[Type["Model"]] = None
        self.manager: Manager = getattr(meta, "manager", Manager())
        self.unique_together: Any = getattr(meta, "unique_together", None)
        self.indexes: Any = getattr(meta, "indexes", None)
        self.reflect: bool = getattr(meta, "reflect", False)
        self.managers: bool = getattr(meta, "_managers", None)
        self.is_multi: bool = getattr(meta, "is_multi", False)
        self.multi_related: Sequence[str] = getattr(meta, "multi_related", [])
        self.related_names: Set[str] = set()
