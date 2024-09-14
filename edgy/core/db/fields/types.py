from __future__ import annotations

import warnings
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, FrozenSet, Optional, Sequence, cast

import sqlalchemy
from pydantic import BaseModel, Field

from edgy.types import Undefined

if TYPE_CHECKING:
    from edgy.core.connection import Registry
    from edgy.core.db.fields.factories import FieldFactory
    from edgy.core.db.models.metaclasses import MetaInfo
    from edgy.core.db.models.types import BaseModelType


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
    constraints: Sequence[sqlalchemy.Constraint] = Field(exclude=True, default=())


class BaseFieldDefinitions:
    read_only: bool = False
    inject_default_on_partial_update: bool = False
    inherit: bool = True
    skip_absorption_check: bool = False
    field_type: Any = Any
    factory: Optional[FieldFactory] = None

    __original_type__: Any = None
    name: str = ""
    secret: bool = False
    exclude: bool = False
    owner: Any = None
    default: Any = Undefined
    server_default: Any = None

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

    def operator_to_clause(
        self, field_name: str, operator: str, table: sqlalchemy.Table, value: Any
    ) -> Any:
        """
        Analyzes the operator and build a clause from it.
        Needs to be able to handle "exact".
        """
        raise NotImplementedError()

    def clean(self, field_name: str, value: Any, for_query: bool = False) -> Dict[str, Any]:
        """
        Validates a value and transform it into columns which can be used for querying and saving.

        Args:
            field_name: the field name (can be different from name)
            value: the field value
        Kwargs:
            for_query: Is used for querying. Should have all columns used for querying set.
                       The columns used can differ especially for multi column fields.
        """
        return {}

    def to_model(
        self,
        field_name: str,
        value: Any,
        phase: str = "",
    ) -> Dict[str, Any]:
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
        self, name: str, columns: Sequence[sqlalchemy.Column], schemes: Sequence[str] = ()
    ) -> Sequence[sqlalchemy.Constraint]:
        """Return global constraints and indexes.
        Useful for multicolumn fields
        """
        return []

    def get_embedded_fields(
        self, field_name: str, fields: Dict[str, BaseFieldType]
    ) -> Dict[str, BaseFieldType]:
        """
        Define extra fields on the fly. Often no owner is available yet.

        Args:
            field_name: the field name (can be different from name)
            fields: the existing fields

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
        owner: Optional[BaseModelType] = None,
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

    @property
    def registry(self) -> Registry:
        warnings.warn(
            "registry attribute of field is deprecated, use 'owner.meta.registry' instead",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.owner.meta.registry  # type: ignore

    def get_column_names(self, name: str = "") -> FrozenSet[str]:
        if name:
            return cast("MetaInfo", self.owner.meta).field_to_column_names[name]
        return cast("MetaInfo", self.owner.meta).field_to_column_names[self.name]
