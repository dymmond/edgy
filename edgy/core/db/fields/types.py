from __future__ import annotations

import warnings
from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, TypedDict, cast

import sqlalchemy
from pydantic import BaseModel, Field

from edgy.types import Undefined

if TYPE_CHECKING:
    from edgy.core.connection import Registry
    from edgy.core.db.fields.factories import FieldFactory
    from edgy.core.db.models.metaclasses import MetaInfo
    from edgy.core.db.models.types import BaseModelType


class FIELD_CONTEXT_TYPE(TypedDict):
    """
    TypedDict for storing field-related context, primarily used for internal Edgy operations.
    """

    field: BaseFieldType


# Mark as total=False as 'field' might not always be present or the only key.
FIELD_CONTEXT_TYPE.__total__ = False


class _ColumnDefinition:
    """
    Internal base class for common SQLAlchemy column-specific definitions.
    Used to prevent shadowing warnings in `ColumnDefinition`.
    """

    # column specific
    primary_key: bool = False
    autoincrement: bool = False
    index: bool = False
    unique: bool = False
    comment: str | None = None
    # Can be Any to allow for complex server-side update expressions (e.g., SQLAlchemy functions).
    server_onupdate: Any | None = None


class ColumnDefinition(_ColumnDefinition):
    """
    Defines the properties of a single database column within an Edgy field.

    This class encapsulates the SQLAlchemy-related attributes that define
    how a field maps to a database column.
    """

    null: bool = False
    column_name: str | None = None
    column_type: Any = None  # The SQLAlchemy type of the column.
    constraints: Sequence[sqlalchemy.Constraint] = ()
    # Can be Any to allow for complex server-side default expressions.
    server_default: Any | None = Undefined


class ColumnDefinitionModel(
    _ColumnDefinition, BaseModel, extra="ignore", arbitrary_types_allowed=True
):
    """
    A Pydantic BaseModel for column definitions, used internally for validation
    and schema generation, while excluding certain fields relevant only to
    SQLAlchemy's column creation.
    """

    # Exclude these fields from Pydantic model representation/serialization,
    # as Edgy handles their logic customly or they're SQLAlchemy-specific.
    column_name: str | None = Field(exclude=True, default=None)
    column_type: Any = Field(exclude=True, default=None)
    constraints: Sequence[sqlalchemy.Constraint] = Field(exclude=True, default=())


class BaseFieldDefinitions:
    """
    Base class for common field definitions across all Edgy field types.

    This class holds properties that describe a field's behavior within
    the Edgy ORM, such as its read-only status, default values, and
    how it interacts with Pydantic and database operations.
    """

    no_copy: bool = False
    read_only: bool = False
    inject_default_on_partial_update: bool = False
    inherit: bool = True
    skip_absorption_check: bool = False
    skip_reflection_type_check: bool = False
    field_type: Any = Any  # The Python type that the field represents.
    factory: FieldFactory | None = None  # The field factory that created this field.

    __original_type__: Any = None
    name: str = ""  # The name of the field on the model.
    secret: bool = False  # If True, the field's value should be treated as sensitive.
    exclude: bool = (
        False  # If True, exclude this field from database operations (e.g., PlaceholderField).
    )
    owner: Any = None  # The Edgy Model class that owns this field.
    default: Any = Undefined  # The Python-side default value for the field.
    explicit_none: bool = (
        False  # If True, `None` is explicitly allowed as a value, even if `null=False`.
    )
    server_default: Any = Undefined  # The database-side default value (e.g., SQL expression).

    # column specific - duplicated from _ColumnDefinition for direct access on BaseFieldDefinitions
    primary_key: bool = False
    autoincrement: bool = False
    null: bool = False
    index: bool = False
    unique: bool = False


class BaseFieldType(BaseFieldDefinitions, ABC):
    """
    Abstract base class for all Edgy field types.

    This class defines the core interface that every Edgy field must implement,
    providing methods for determining field requirements, handling defaults,
    generating SQLAlchemy columns, cleaning/converting values, and more.
    """

    @abstractmethod
    def is_required(self) -> bool:
        """
        Abstract method to check if the field is required.

        Returns:
            `True` if the field must have a value, `False` otherwise.
        """

    @abstractmethod
    def has_default(self) -> bool:
        """
        Abstract method to check if the field has a default value set.

        Returns:
            `True` if a default is provided (Python-side or server-side), `False` otherwise.
        """

    @abstractmethod
    def get_columns(self, field_name: str) -> Sequence[sqlalchemy.Column]:
        """
        Abstract method to return the SQLAlchemy `Column` objects corresponding to this field.

        A field might map to one or more database columns (e.g., a composite field).

        Args:
            field_name (str): The logical name of the field on the model.

        Returns:
            Sequence[sqlalchemy.Column]: A sequence of SQLAlchemy Column objects.
        """

    def operator_to_clause(
        self, field_name: str, operator: str, table: sqlalchemy.Table, value: Any
    ) -> Any:
        """
        Analyzes a query operator and constructs a SQLAlchemy clause from it.

        This method is crucial for building database queries. It should handle
        various operators (e.g., "exact", "iexact", "gt", "lt").

        Args:
            field_name (str): The name of the field being queried.
            operator (str): The query operator (e.g., "exact", "gt").
            table (sqlalchemy.Table): The SQLAlchemy Table object corresponding to the model.
            value (Any): The value to use in the comparison.

        Returns:
            Any: A SQLAlchemy clause (e.g., `Column.operate()`, `Column == value`).

        Raises:
            NotImplementedError: If the method is not implemented by a concrete field.
        """
        raise NotImplementedError()

    def clean(self, field_name: str, value: Any, for_query: bool = False) -> dict[str, Any]:
        """
        Validates and transforms a Python value into a format suitable for database operations.

        This method is used when preparing data for insertion or update into the database,
        or when building query predicates. Multi-column fields should return a dictionary
        mapping column names to their cleaned values.

        Args:
            field_name (str): The logical name of the field.
            value (Any): The Python value of the field.
            for_query (bool): If `True`, the cleaning is for query construction; otherwise, for saving.

        Returns:
            dict[str, Any]: A dictionary where keys are database column names and values are
                            their cleaned representations.
        """
        return {}

    def to_model(
        self,
        field_name: str,
        value: Any,
    ) -> dict[str, Any]:
        """
        Converts database column values back into the Python representation for the Edgy model.

        This is the inverse of `clean`. It takes raw values retrieved from the database
        and transforms them into the expected Python type for the model instance.

        Args:
            field_name (str): The logical name of the field.
            value (Any): The raw value(s) retrieved from the database.

        Returns:
            dict[str, Any]: A dictionary where keys are field names and values are
                            their Python representations.
        """
        return {field_name: value}

    def get_global_constraints(
        self,
        name: str,
        columns: Sequence[sqlalchemy.Column],
        schemes: Sequence[str] = (),
    ) -> Sequence[sqlalchemy.Constraint | sqlalchemy.Index]:
        """
        Returns global SQLAlchemy constraints or indexes that apply across multiple columns
        or at the table level (e.g., unique constraints involving multiple fields).

        Args:
            name (str): The logical name of the field.
            columns (Sequence[sqlalchemy.Column]): The SQLAlchemy Column objects associated with this field.
            schemes (Sequence[str]): Database schema names (if applicable).

        Returns:
            Sequence[sqlalchemy.Constraint | sqlalchemy.Index]: A sequence of SQLAlchemy constraints or indexes.
        """
        return []

    def get_embedded_fields(
        self, field_name: str, fields: dict[str, BaseFieldType]
    ) -> dict[str, BaseFieldType]:
        """
        Defines and returns additional fields that should be "embedded" or added
        to the model's schema dynamically.

        This is useful for fields that generate related or sub-fields. The returned
        fields should be new instances or copies, and their `owner` should be set.

        Args:
            field_name (str): The logical name of the field.
            fields (dict[str, BaseFieldType]): The existing fields defined on the model.

        Returns:
            dict[str, BaseFieldType]: A dictionary of new field names to `BaseFieldType` instances.
        """
        return {}

    @abstractmethod
    def get_default_values(self, field_name: str, cleaned_data: dict[str, Any]) -> Any:
        """
        Abstract method to provide default values for the field or its constituent columns.

        This method is responsible for generating default values that are applied during
        model initialization or database operations. For multi-column fields, it should
        check `cleaned_data` to avoid re-applying defaults if values are already present.

        Args:
            field_name (str): The logical name of the field.
            cleaned_data (dict[str, Any]): The currently validated data, useful for
                                          checking if defaults have already been applied.

        Returns:
            Any: The default value(s) for the field.
        """

    @abstractmethod
    def embed_field(
        self,
        prefix: str,
        new_fieldname: str,
        owner: BaseModelType | None = None,
        parent: BaseFieldType | None = None,
    ) -> BaseFieldType | None:
        """
        Abstract method to "embed" this field under a new name and/or with a prefix.

        Embedding typically creates a copy of the field with adjusted properties
        (like name and owner) to support nested relationships or complex data structures
        within a model. If `None` is returned, embedding is prevented.

        Args:
            prefix (str): A string prefix to be added to the new field's column name(s).
            new_fieldname (str): The desired new logical name for the embedded field.
            owner (BaseModelType | None): The new owner model for the embedded field.
            parent (BaseFieldType | None): The parent field that is performing the embedding.

        Returns:
            BaseFieldType | None: A copy of the field with updated properties, or `None`
                                 if embedding is not supported or desired.
        """

    # helpers

    @property
    def registry(self) -> Registry:
        """
        (Deprecated) Provides access to the Edgy `Registry` associated with the field's owner model.

        This property is deprecated; use `self.owner.meta.registry` instead.
        """
        warnings.warn(
            "registry attribute of field is deprecated, use 'owner.meta.registry' instead",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.owner.meta.registry  # type: ignore

    def get_column_names(self, name: str = "") -> frozenset[str]:
        """
        Retrieves the set of database column names associated with this field.

        Args:
            name (str): The logical name of the field. If empty, uses `self.name`.

        Returns:
            frozenset[str]: A frozenset of database column names.
        """
        if name:
            return cast("MetaInfo", self.owner.meta).field_to_column_names[name]
        return cast("MetaInfo", self.owner.meta).field_to_column_names[self.name]
