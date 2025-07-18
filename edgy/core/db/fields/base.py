from __future__ import annotations

import contextlib
import copy
from abc import abstractmethod
from collections.abc import Sequence
from functools import cached_property
from typing import (
    TYPE_CHECKING,
    Any,
    Literal,
    cast,
)

import sqlalchemy
from pydantic import BaseModel, SkipValidation
from pydantic.fields import FieldInfo
from pydantic.json_schema import WithJsonSchema

from edgy.conf import settings
from edgy.core.db.context_vars import (
    CURRENT_PHASE,
    FALLBACK_TARGET_REGISTRY,
    FORCE_FIELDS_NULLABLE,
    MODEL_GETATTR_BEHAVIOR,
)
from edgy.types import Undefined

from .types import BaseFieldType, ColumnDefinitionModel

if TYPE_CHECKING:
    from edgy.core.connection.database import Database
    from edgy.core.connection.registry import Registry
    from edgy.core.db.models.types import BaseModelType


class BaseField(BaseFieldType, FieldInfo):
    """
    The base field for Edgy data model fields. It provides some helpers additional to
    BaseFieldType and inherits from FieldInfo for pydantic integration.

    Allows factories to overwrite methods.
    """

    owner: type[BaseModelType]
    operator_mapping: dict[str, str] = {
        "is": "is_",
        "in": "in_",
        "exact": "__eq__",
        "not": "__ne__",
        "gt": "__gt__",
        "ge": "__ge__",
        "gte": "__ge__",
        "lt": "__lt__",
        "lte": "__le__",
        "le": "__le__",
    }
    auto_compute_server_default: bool | None | Literal["ignore_null"] = False

    def __init__(
        self,
        *,
        default: Any = Undefined,
        server_default: Any = Undefined,
        **kwargs: Any,
    ) -> None:
        if "__type__" in kwargs:
            kwargs["field_type"] = kwargs.pop("__type__")
        self.explicit_none = default is None
        self.server_default = server_default

        super().__init__(**kwargs)

        # set remaining attributes
        for name, value in kwargs.items():
            setattr(self, name, value)

        # null is used for nullable columns and is_required is False
        # this is required for backward compatibility and pydantic_core uses null=True too
        # for opting out of nullable columns overwrite the get_column(s) method
        if (
            self.null
            or (self.server_default is not None and self.server_default is not Undefined)
            or self.autoincrement
        ) and default is Undefined:
            default = None
        if default is not Undefined:
            self.default = default

    def get_server_default(self) -> Any:
        """
        Retrieve the server_default.
        """
        server_default = getattr(self, "server_default", Undefined)
        # check if there was an explicit defined server_default
        if server_default is not Undefined:
            return server_default
        default = self.default
        if default is Undefined or default is None:
            return None
        if not callable(default):
            if self.auto_compute_server_default is None:
                auto_compute_server_default: bool = (
                    not self.null and settings.allow_auto_compute_server_defaults
                )
            elif self.auto_compute_server_default == "ignore_null":
                auto_compute_server_default = settings.allow_auto_compute_server_defaults
            else:
                auto_compute_server_default = self.auto_compute_server_default
        else:
            auto_compute_server_default = self.auto_compute_server_default is True

        if auto_compute_server_default:
            return self.customize_default_for_server_default(default)
        return None

    def customize_default_for_server_default(self, default: Any) -> Any:
        """
        Modify default for non-null server_default.

        Args:
            default: The original default.

        """
        if callable(default):
            default = default()
        return sqlalchemy.text(":value").bindparams(value=default)

    def get_columns_nullable(self) -> bool:
        """
        Helper method.
        Returns if the columns of the field should be nullable.
        """
        if self.null:
            return True
        force_fields = FORCE_FIELDS_NULLABLE.get()
        return (self.owner.__name__, self.name) in force_fields or ("", self.name) in force_fields

    def operator_to_clause(
        self, field_name: str, operator: str, table: sqlalchemy.Table, value: Any
    ) -> Any:
        """
        Converts a given operator and value into a SQLAlchemy clause for filtering.

        This method maps common operation codes to SQLAlchemy's ColumnElement methods,
        allowing for dynamic construction of database queries. It handles special cases
        like case-insensitive exact matches ('iexact') and null checks ('isnull'),
        as well as various string containment operations.

        Args:
            field_name: The name of the column to apply the operator to.
            operator: The operation code (e.g., 'iexact', 'contains', 'isnull').
            table: The SQLAlchemy Table object the column belongs to.
            value: The value to compare against.

        Returns:
            A SQLAlchemy clause suitable for use in a query's WHERE statement.

        Raises:
            KeyError: If 'field_name' does not correspond to an existing column in the table.
            AttributeError: If the mapped operator does not exist as a method on the column.
        """
        column = table.columns[field_name]
        mapped_operator = self.operator_mapping.get(operator, operator)

        if mapped_operator == "iexact":
            # Handle case-insensitive exact matching with escape character logic
            escape_characters = ["%", "_"]
            has_escaped_character = any(char in value for char in escape_characters)

            if has_escaped_character:
                # Escape backslashes first, then the specific escape characters
                processed_value = value.replace("\\", "\\\\")
                for char in escape_characters:
                    processed_value = processed_value.replace(char, f"\\{char}")
                return column.ilike(processed_value, escape="\\")
            else:
                return column.ilike(value)

        elif mapped_operator == "isnull":
            # Handle isnull/isnotnull operations
            return column.is_(None) if value is True else column.isnot(None)

        elif mapped_operator in {
            "contains",
            "icontains",
            "startswith",
            "endswith",
            "istartswith",
            "iendswith",
        }:
            # Handle various string matching operations with autoescape
            return getattr(column, mapped_operator)(value, autoescape=True)

        else:
            # Default case: directly apply the operator if it's a ColumnElement method
            return getattr(column, mapped_operator)(value)

    def is_required(self) -> bool:
        """Check if the argument is required.

        Returns:
            `True` if the argument is required, `False` otherwise.
        """
        if self.primary_key and self.autoincrement:
            return False
        return not (
            self.null
            # we cannot use get_server_default() here. The test is client side not for migrations.
            or (self.server_default is not None and self.server_default is not Undefined)
            or self.has_default()
        )

    def has_default(self) -> bool:
        """Checks if the field has a default value set"""
        return bool(
            (self.default is not None or self.explicit_none) and self.default is not Undefined
        )

    def get_columns(self, name: str) -> Sequence[sqlalchemy.Column]:
        """
        Returns the columns of the field being declared.
        """
        return []

    def embed_field(
        self,
        prefix: str,
        new_fieldname: str,
        owner: type[BaseModelType] | None = None,
        parent: BaseFieldType | None = None,
    ) -> BaseField | None:
        """
        Embed this field or return None to prevent embedding.
        Must return a copy with name and owner set when not returning None.
        """
        field_copy = copy.copy(self)
        field_copy.name = new_fieldname
        field_copy.owner = owner
        if getattr(parent, "prefix_column_name", None):
            if getattr(field_copy, "column_name", None):
                field_copy.column_name = f"{parent.prefix_column_name}{field_copy.column_name}"  # type: ignore
            else:
                field_copy.column_name = (
                    f"{parent.prefix_column_name}{new_fieldname[len(prefix) :]}"  # type: ignore
                )

        return field_copy

    def get_default_value(self) -> Any:
        # single default
        default = getattr(self, "default", None)
        if callable(default):
            return default()
        return default

    def get_default_values(self, field_name: str, cleaned_data: dict[str, Any]) -> dict[str, Any]:
        # for multidefaults overwrite in subclasses get_default_values to
        # parse default values differently
        # NOTE: multi value fields should always check here if defaults were already applied
        # NOTE: when build meta fields without columns this should be empty
        if field_name in cleaned_data:
            return {}
        return {field_name: self.get_default_value()}


class Field(BaseField):
    """
    Single column field used by factories.
    """

    # safe here as we have only one column
    auto_compute_server_default: bool | None | Literal["ignore_null"] = None

    def check(self, value: Any) -> Any:
        """
        Runs the checks for the fields being validated. Single Column.
        """
        return value

    def clean(self, name: str, value: Any, for_query: bool = False) -> dict[str, Any]:
        """
        Converts a field value via check method to a column value.
        """
        return {name: self.check(value)}

    def get_column(self, name: str) -> sqlalchemy.Column | None:
        """
        Return a single column for the field declared. Return None for meta fields.
        """
        column_model = ColumnDefinitionModel.model_validate(self, from_attributes=True)
        if column_model.column_type is None:
            return None
        return sqlalchemy.Column(
            column_model.column_name or name,
            column_model.column_type,
            *column_model.constraints,
            key=name,
            nullable=self.get_columns_nullable(),
            server_default=self.get_server_default(),
            **column_model.model_dump(by_alias=True, exclude_none=True),
        )

    def get_columns(self, name: str) -> Sequence[sqlalchemy.Column]:
        """
        Return the single column from get_column for the field declared.
        """
        column = self.get_column(name)
        if column is None:
            return []
        return [column]


class BaseCompositeField(BaseField):
    def translate_name(self, name: str) -> str:
        """translate name for inner objects and parsing values"""
        return name

    def get_composite_fields(self) -> dict[str, BaseFieldType]:
        """return dictionary of fields with untranslated names"""
        raise NotImplementedError()

    @cached_property
    def composite_fields(self) -> dict[str, BaseFieldType]:
        # return untranslated names
        return self.get_composite_fields()

    def clean(self, field_name: str, value: Any, for_query: bool = False) -> dict[str, Any]:
        """
        Runs the checks for the fields being validated.
        """
        prefix = field_name.removesuffix(self.name)
        result: dict[str, Any] = {}
        ErrorType: type[Exception] = KeyError

        # None has no __dict__
        if value is None:
            return result
        if not isinstance(value, dict):
            # simpler
            value = value.__dict__
            # trigger load for missing attributes
            ErrorType = AttributeError

        for sub_name, field in self.composite_fields.items():
            translated_name = self.translate_name(sub_name)
            if translated_name not in value:
                if field.has_default() or not field.is_required():
                    continue
                raise ErrorType(f"Missing sub-field: {sub_name} for {field_name}")
            result.update(
                field.clean(f"{prefix}{sub_name}", value[translated_name], for_query=for_query)
            )
        return result

    def to_model(
        self,
        field_name: str,
        value: Any,
    ) -> dict[str, Any]:
        """
        Runs the checks for the fields being validated.
        """
        result = {}
        phase = CURRENT_PHASE.get()
        ErrorType: type[Exception] = KeyError
        if not isinstance(value, dict):
            # simpler
            value = value.__dict__
            # trigger load for missing attributes
            ErrorType = AttributeError
        for sub_name, field in self.composite_fields.items():
            translated_name = self.translate_name(sub_name)
            if translated_name not in value:
                if phase == "init" or phase == "init_db":
                    continue
                raise ErrorType(f"Missing sub-field: {sub_name} for {field_name}")
            result.update(field.to_model(sub_name, value.get(translated_name, None)))
        return result

    def get_default_values(self, field_name: str, cleaned_data: dict[str, Any]) -> Any:
        # fields should provide their own default which is used as long as they are in the fields mapping
        return {}


class RelationshipField(BaseField):
    def traverse_field(self, path: str) -> tuple[Any, str, str]:
        raise NotImplementedError()

    def is_cross_db(self, owner_database: Database | None = None) -> bool:
        raise NotImplementedError()

    def get_related_model_for_admin(self) -> BaseModelType | None:
        raise NotImplementedError()


class PKField(BaseCompositeField):
    """
    Field for pk
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs["default"] = None
        kwargs["field_type"] = kwargs["annotation"] = Any
        super().__init__(**kwargs)
        self.metadata.append(SkipValidation())
        self.metadata.append(WithJsonSchema(mode="validation", json_schema=None))

    def __get__(self, instance: BaseModelType, owner: Any = None) -> dict[str, Any] | Any:
        pkcolumns = self.owner.pkcolumns
        pknames = self.owner.pknames
        assert len(pkcolumns) >= 1
        # we don't want to issue loads
        token = MODEL_GETATTR_BEHAVIOR.set("passdown")
        try:
            if len(pknames) == 1:
                return getattr(instance, pknames[0], None)
            d = {}
            for key in pknames:
                translated_name = self.translate_name(key)
                field = instance.meta.fields.get(key)
                if field and hasattr(field, "__get__"):
                    d[translated_name] = field.__get__(instance, owner)
                else:
                    d[translated_name] = getattr(instance, key, None)
            for key in self.fieldless_pkcolumns:
                translated_name = self.translate_name(key)
                d[translated_name] = getattr(instance, key, None)
        finally:
            MODEL_GETATTR_BEHAVIOR.reset(token)
        return d

    def modify_input(self, name: str, kwargs: dict[str, Any]) -> None:
        if name not in kwargs:
            return
        # check for collisions
        for pkname in self.owner.pknames:
            if pkname in kwargs:
                raise ValueError("Cannot specify a primary key field and the primary key itself")

    def embed_field(
        self,
        prefix: str,
        new_fieldname: str,
        owner: type[BaseModelType] | None = None,
        parent: BaseFieldType | None = None,
    ) -> BaseFieldType | None:
        return None

    def clean(self, field_name: str, value: Any, for_query: bool = False) -> dict[str, Any]:
        pkcolumns = self.owner.pkcolumns
        pknames = self.owner.pknames
        prefix = field_name.removesuffix(self.name)
        assert len(pkcolumns) >= 1
        if (
            len(pknames) == 1
            and not self.is_incomplete
            and not isinstance(value, dict | BaseModel)
        ):
            pkname = pknames[0]
            field = self.owner.meta.fields[pkname]
            return field.clean(f"{prefix}{pkname}", value, for_query=for_query)
        retdict = super().clean(field_name, value, for_query=for_query)
        if self.is_incomplete:
            if isinstance(value, dict):
                for column_name in self.fieldless_pkcolumns:
                    translated_name = self.translate_name(column_name)
                    if translated_name not in value:
                        if not for_query:
                            continue
                        raise ValueError(f"Missing key: {translated_name} for {field_name}")
                    retdict[f"{prefix}{column_name}"] = value[translated_name]
            else:
                for column_name in self.fieldless_pkcolumns:
                    translated_name = self.translate_name(column_name)
                    if not hasattr(value, translated_name):
                        if not for_query:
                            continue
                        raise ValueError(f"Missing attribute: {translated_name} for {field_name}")
                    retdict[f"{prefix}{column_name}"] = getattr(value, translated_name)

        return retdict

    def to_model(
        self,
        field_name: str,
        value: Any,
    ) -> dict[str, Any]:
        pknames = self.owner.pknames
        assert len(self.owner.pkcolumns) >= 1
        if self.is_incomplete:
            raise ValueError("Cannot set an incomplete defined pk!")
        if (
            len(pknames) == 1
            # we first only redirect both
            and not isinstance(value, dict | BaseModel)
        ):
            field = self.owner.meta.fields[pknames[0]]
            return field.to_model(pknames[0], value)
        return super().to_model(field_name, value)

    def get_composite_fields(self) -> dict[str, BaseFieldType]:
        return {field: self.owner.meta.fields[field] for field in self.owner.pknames}

    @cached_property
    def fieldless_pkcolumns(self) -> frozenset[str]:
        field_less = set()
        for colname in self.owner.pkcolumns:
            if colname not in self.owner.meta.columns_to_field:
                field_less.add(colname)
        return frozenset(field_less)

    @property
    def is_incomplete(self) -> bool:
        return bool(self.fieldless_pkcolumns)

    def is_required(self) -> bool:
        return False


class BaseForeignKey(RelationshipField):
    is_m2m: bool = False
    related_name: str | Literal[False] = ""
    # name used for backward relations
    # only useful if related_name = False because otherwise it gets overwritten
    reverse_name: str = ""

    @property
    def target_registry(self) -> Registry:
        """Registry searched in case to is a string"""

        if not hasattr(self, "_target_registry"):
            target_registry: Registry | None | Literal[False] = self.owner.meta.registry
            # when an abstract model is used for CompositeField we have no registry but a model() call
            # this provides a fallback
            if target_registry is None:
                target_registry = FALLBACK_TARGET_REGISTRY.get()
            assert target_registry, (
                f"{self.owner} ({self.name}): no registry found, "
                "nor FALLBACK_TARGET_REGISTRY found, nor 'target_registry' set"
            )
            return target_registry
        return cast("Registry", self._target_registry)

    @target_registry.setter
    def target_registry(self, value: Any) -> None:
        self._target_registry = value

    @target_registry.deleter
    def target_registry(self) -> None:
        with contextlib.suppress(AttributeError):
            delattr(self, "_target_registry")

    @property
    def target(self) -> Any:
        """
        The target of the ForeignKey model.
        """
        if not hasattr(self, "_target"):
            if isinstance(self.to, str):
                self._target = self.target_registry.get_model(self.to)
            else:
                self._target = self.to
        return self._target

    @target.setter
    def target(self, value: Any) -> None:
        with contextlib.suppress(AttributeError):
            delattr(self, "_target")
        self.to = value

    @target.deleter
    def target(self) -> None:
        # clear cache
        with contextlib.suppress(AttributeError):
            delattr(self, "_target")

    def is_cross_db(self, owner_database: Database | None = None) -> bool:
        if owner_database is None:
            owner_database = self.owner.database
        return str(owner_database.url) != str(self.target.database.url)

    def get_related_model_for_admin(self) -> type[BaseModelType] | None:
        if self.target.__name__ in self.target_registry.admin_models:
            return cast("type[BaseModelType]", self.target)
        return None

    @abstractmethod
    def reverse_clean(self, name: str, value: Any, for_query: bool = False) -> dict[str, Any]: ...

    def expand_relationship(self, value: Any) -> Any:
        """
        Returns the related object or the relationship object
        """
        return value

    def to_model(
        self,
        field_name: str,
        value: Any,
    ) -> dict[str, Any]:
        return {field_name: self.expand_relationship(value)}
