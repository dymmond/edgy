from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, FrozenSet, Optional, Sequence, cast

import sqlalchemy
from pydantic import BaseModel, Field

from edgy.core.connection.registry import Registry
from edgy.types import Undefined

if TYPE_CHECKING:
    from edgy.core.db.models.base import EdgyBaseModel
    from edgy.core.db.models.metaclasses import MetaInfo


class _ColumnDefinition:
    # column specific
    primary_key: bool = False
    autoincrement: bool = False
    index: bool = False
    unique: bool = False
    default: Any = None
    comment: Optional[str] = None
    server_default: Optional[Any] = None
    server_onupdate: Optional[Any] = None


# for preventing shadowing warnings
class ColumnDefinition(_ColumnDefinition):
    null: bool = False
    column_name: Optional[str] = None
    column_type: Any = None
    constraints: Sequence[sqlalchemy.Constraint] = ()


class ColumnDefinitionModel(
    _ColumnDefinition, BaseModel, extra="ignore", arbitrary_types_allowed=True
):
    null: bool = Field(serialization_alias="nullable", default=False)
    column_name: Optional[str] = Field(exclude=True, default=None)
    column_type: Any = Field(exclude=True, default=None)
    constraints: Sequence[sqlalchemy.Constraint] = Field(exclude=True, default=tuple)  # type: ignore


class BaseFieldDefinitions:
    read_only: bool = False
    inject_default_on_partial_update: bool = False
    inherit: bool = True
    skip_absorption_check: bool = False
    factory: Any = None
    registry: Optional[Registry] = None
    field_type: Any = Any
    __original_type__: Any = None
    name: str = ""
    secret: bool = False
    exclude: bool = False
    owner: Any = None
    default: Any = Undefined

    # column specific
    primary_key: bool = False
    autoincrement: bool = False
    null: bool = False
    index: bool = False
    unique: bool = False


class BaseFieldType(BaseFieldDefinitions, ABC):
    @abstractmethod
    def is_required(self) -> bool:
        """Check if the argument is required.

        Returns:
            `True` if the argument is required, `False` otherwise.
        """

    @abstractmethod
    def has_default(self) -> bool:
        """Checks if the field has a default value set"""

    @abstractmethod
    def get_columns(self, field_name: str) -> Sequence[sqlalchemy.Column]:
        """
        Returns the columns of the field being declared.
        """

    def clean(self, field_name: str, value: Any, for_query: bool = False) -> Dict[str, Any]:
        """
        Validates a value and transform it into columns which can be used for querying and saving.

        Args:
            field_name: the field name (can be different from name)
            value: the field value
        Kwargs:
            for_query: is used for querying. Should have all columns used for querying set.
        """
        return {}

    def to_model(self, field_name: str, value: Any, phase: str = "") -> Dict[str, Any]:
        """
        Inverse of clean. Transforms column(s) to a field for a pydantic model (EdgyBaseModel).
        Validation happens later.

        Args:
            field_name: the field name (can be different from name)
            value: the field value
        Kwargs:
            phase: the phase (set, creation, ...)

        """
        return {field_name: value}

    def get_global_constraints(
        self, name: str, columns: Sequence[sqlalchemy.Column]
    ) -> Sequence[sqlalchemy.Constraint]:
        """Return global constraints and indexes.
        Useful for multicolumn fields
        """
        return []

    def get_embedded_fields(
        self, field_name: str, fields_mapping: Dict[str, BaseFieldType]
    ) -> Dict[str, BaseFieldType]:
        """
        Define extra fields on the fly. Often no owner is available yet.

        Args:
            field_name: the field name (can be different from name)
            fields_mapping: the existing fields

        Note: the returned fields are changed after return, so you should
              return new fields or copies. Also set the owner of the field to them before returning
        """
        return {}

    @abstractmethod
    def get_default_values(
        self, field_name: str, cleaned_data: Dict[str, Any], is_update: bool = False
    ) -> Any:
        """
        Define for each field/column a default. Non-private multicolumn fields should
        always check if the default was already applied.

        Args:
            field_name: the field name (can be different from name)
            cleaned_data: currently validated data. Useful to check if the default was already applied.
        Kwargs:
            is_update: phase. Is update phase or is creation phase. For e.g. autonow_add

        """

    @abstractmethod
    def embed_field(
        self,
        prefix: str,
        new_fieldname: str,
        owner: Optional[EdgyBaseModel] = None,
        parent: Optional[BaseFieldType] = None,
    ) -> Optional[BaseFieldType]:
        """
        Embed this field or return None to prevent embedding.
        Must return a copy with name and owner set when not returning None.
        Args:
            prefix: the prefix
            new_field_name: the new field name
            owner: The new owner if available
            parent: The parent field which embeds the field if available
        """

    # helpers

    def get_column_names(self, name: str = "") -> FrozenSet[str]:
        if name:
            return cast("MetaInfo", self.owner.meta).field_to_column_names[name]
        return cast("MetaInfo", self.owner.meta).field_to_column_names[self.name]
