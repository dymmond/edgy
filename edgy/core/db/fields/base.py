from __future__ import annotations

import contextlib
import copy
from abc import abstractmethod
from collections.abc import Sequence
from functools import cached_property
from typing import TYPE_CHECKING, Any, Literal, cast

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
    The foundational class for all Edgy model fields.

    This class extends `BaseFieldType` and `pydantic.fields.FieldInfo` to provide
    core functionalities for defining model attributes, including database column
    mapping, validation, and default value handling. It also offers mechanisms
    for dynamic operator mapping for query building.

    Attributes:
        owner: The model class to which this field belongs.
        operator_mapping: A dictionary mapping common operator strings to
                          SQLAlchemy's `ColumnElement` methods for query construction.
        auto_compute_server_default: Controls the automatic computation of server
                                     defaults. Can be `True`, `False`, `None`, or
                                     "ignore_null". `None` means use global settings,
                                     "ignore_null" means ignore nullability for auto-computation.
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
        """
        Initializes a new `BaseField` instance.

        This constructor processes default values, server defaults, and other
        field configurations, integrating them with Pydantic's `FieldInfo`.

        Args:
            default: The default Python value for the field. If `Undefined`,
                     no Python default is set.
            server_default: The default value to be set by the database server.
                            If `Undefined`, no server default is explicitly set.
            **kwargs: Additional keyword arguments to be passed to `FieldInfo`
                      and stored as attributes of the field.
        """
        # If '__type__' is provided in kwargs, rename it to 'field_type'.
        if "__type__" in kwargs:
            kwargs["field_type"] = kwargs.pop("__type__")
        # Determine if 'None' was explicitly provided as a default.
        self.explicit_none = default is None
        # Store the server_default.
        self.server_default = server_default

        # Call the parent FieldInfo constructor with remaining kwargs.
        super().__init__(**kwargs)

        # Set any remaining keyword arguments as attributes of the field instance.
        for name, value in kwargs.items():
            setattr(self, name, value)

        # If the field is nullable, has a server default, or is autoincrementing,
        # and no default was explicitly provided, set the default to None.
        # This ensures backward compatibility and aligns with pydantic_core's
        # handling of nullable columns.
        if (
            self.null
            or (self.server_default is not None and self.server_default is not Undefined)
            or self.autoincrement
        ) and default is Undefined:
            default = None
        # If a default value was determined (either provided or set to None),
        # apply it to the field.
        if default is not Undefined:
            self.default = default

    def get_server_default(self) -> Any:
        """
        Retrieves the server-side default value for the column.

        This method determines the appropriate server default, considering
        explicitly defined `server_default`, the field's `default` value,
        and the `auto_compute_server_default` setting.

        Returns:
            The server default value, which can be `None`, a literal value,
            or a SQLAlchemy text construct.
        """
        # Get the explicitly defined server_default.
        server_default = getattr(self, "server_default", Undefined)
        # If an explicit server_default was provided, return it.
        if server_default is not Undefined:
            return server_default

        # Get the Python default value.
        default = self.default
        # If the Python default is Undefined or None, there's no server default to compute.
        if default is Undefined or default is None:
            return None

        # Determine if auto-computation of server default is enabled based on
        # field settings and global configuration.
        if not callable(default):
            if self.auto_compute_server_default is None:
                # If auto_compute_server_default is None, use global settings and nullability.
                auto_compute_server_default: bool = (
                    not self.null and settings.allow_auto_compute_server_defaults
                )
            elif self.auto_compute_server_default == "ignore_null":
                # If "ignore_null", use global settings regardless of nullability.
                auto_compute_server_default = settings.allow_auto_compute_server_defaults
            else:
                # Otherwise, use the explicit auto_compute_server_default setting.
                auto_compute_server_default = self.auto_compute_server_default
        else:
            # If the default is a callable, auto_compute_server_default must be explicitly True.
            auto_compute_server_default = self.auto_compute_server_default is True

        # If auto-computation is enabled, customize the default for server use; otherwise, return None.
        if auto_compute_server_default:
            return self.customize_default_for_server_default(default)
        return None

    def customize_default_for_server_default(self, default: Any) -> Any:
        """
        Customizes the default value for use as a server-side default.

        This method ensures that callable defaults are executed and that
        the resulting value is wrapped in a `sqlalchemy.text` construct
        for appropriate server-side default handling.

        Args:
            default: The original default Python value, which might be a callable.

        Returns:
            A `sqlalchemy.text` object or a literal value suitable for a
            server-side default.
        """
        # If the default is a callable, execute it to get the actual value.
        if callable(default):
            default = default()
        # Wrap the default value in a SQLAlchemy text construct with a bind parameter.
        return sqlalchemy.text(":value").bindparams(value=default)

    def get_columns_nullable(self) -> bool:
        """
        Determines if the database column(s) corresponding to this field should be nullable.

        This method considers the field's explicit `null` setting and global
        `FORCE_FIELDS_NULLABLE` context variable.

        Returns:
            `True` if the column(s) should be nullable, `False` otherwise.
        """
        # If the field is explicitly nullable, return True.
        if self.null:
            return True
        # Get the set of fields that are forced to be nullable globally.
        force_fields = FORCE_FIELDS_NULLABLE.get()
        # Check if the current field (by owner name and field name, or by just field name)
        # is present in the forced nullable fields.
        return (self.owner.__name__, self.name) in force_fields or ("", self.name) in force_fields

    def operator_to_clause(
        self, field_name: str, operator: str, table: sqlalchemy.Table, value: Any
    ) -> Any:
        """
        Converts a given operator and value into a SQLAlchemy clause for filtering.

        This method maps common operation codes to SQLAlchemy's `ColumnElement` methods,
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
        # Get the SQLAlchemy Column object from the table using the field_name.
        column = table.columns[field_name]
        # Get the mapped operator from the operator_mapping, or use the original operator if not found.
        mapped_operator = self.operator_mapping.get(operator, operator)

        # Handle 'iexact' (case-insensitive exact match) specifically.
        match mapped_operator:
            case "iexact":
                # Define characters that need to be escaped in LIKE/ILIKE patterns.
                escape_characters = ["%", "_"]
                # Check if the value contains any of the escape characters.
                has_escaped_character = any(char in value for char in escape_characters)

                if has_escaped_character:
                    # If escaped characters are present, escape backslashes first, then the specific escape characters.
                    processed_value = value.replace("\\", "\\\\")
                    for char in escape_characters:
                        processed_value = processed_value.replace(char, f"\\{char}")
                    # Use ilike with an explicit escape character.
                    return column.ilike(processed_value, escape="\\")
                else:
                    # If no escape characters, use ilike directly.
                    return column.ilike(value)
            case "isnull" | "isempty":
                # Handle 'isnull' (checking for NULL values).
                isnull = column == None  # noqa: E711
                # is_(None) doesn't work for all fields
                # column == None is required for IPAddressField, DateField, DateTimeField
                return isnull if value else sqlalchemy.not_(isnull)

            # Handle various string containment and prefix/suffix matching operations.
            case (
                "contains" | "icontains" | "startswith" | "endswith" | "istartswith" | "iendswith"
            ):
                # Apply the column method with autoescape enabled.
                return getattr(column, mapped_operator)(value, autoescape=True)

            case _:
                # For all other operators, directly apply the corresponding method
                # from the SQLAlchemy column object.
                return getattr(column, mapped_operator)(value)

    def is_required(self) -> bool:
        """
        Checks if the field is required for model instantiation and database inserts.

        A field is considered not required if it's a primary key with autoincrement,
        is nullable, has a server default, or has a Python default.

        Returns:
            `True` if the field is required, `False` otherwise.
        """
        # If the field is a primary key and is autoincrementing, it's not required.
        if self.primary_key and self.autoincrement:
            return False
        # The field is not required if it is nullable, has a server default (explicitly set),
        # or has a Python default.
        return not (
            self.null
            # Check if server_default is explicitly set and not Undefined.
            or (self.server_default is not None and self.server_default is not Undefined)
            or self.has_default()
        )

    def has_default(self) -> bool:
        """
        Checks if the field has a default value set in Python.

        This includes cases where `default` is `None` but explicitly set.

        Returns:
            `True` if a Python default is set, `False` otherwise.
        """
        # A default exists if it's not None (unless explicit_none is True) and it's not Undefined.
        return bool(
            (self.default is not None or self.explicit_none) and self.default is not Undefined
        )

    def get_columns(self, name: str) -> Sequence[sqlalchemy.Column]:
        """
        Returns a sequence of SQLAlchemy Column objects associated with this field.

        This is a base implementation that returns an empty list, as `BaseField`
        itself doesn't directly correspond to columns. Subclasses like `Field`
        will override this to return actual columns.

        Args:
            name: The name of the field.

        Returns:
            An empty sequence of SQLAlchemy Column objects.
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
        Embeds this field into a new context, potentially modifying its name
        and owner.

        This method creates a copy of the field and updates its `name` and `owner`
        attributes. If a `parent` field specifies `prefix_column_name`, it
        updates the `column_name` of the copied field accordingly. Returns `None`
        if embedding is not supported for this field type.

        Args:
            prefix: The prefix to be added to the field's new name.
            new_fieldname: The new full name of the field after embedding.
            owner: The new owner model class for the embedded field.
            parent: The parent field if this field is being embedded within another
                    composite field.

        Returns:
            A copy of the field with updated `name` and `owner`, or `None` if
            embedding is not permitted.
        """
        # Create a shallow copy of the field.
        field_copy = copy.copy(self)
        # Update the name of the copied field.
        field_copy.name = new_fieldname
        # Set the new owner for the copied field.
        field_copy.owner = owner
        # If the parent field has a prefix_column_name attribute, apply it.
        if getattr(parent, "prefix_column_name", None):
            # If the copied field already has a column_name, prefix it.
            if getattr(field_copy, "column_name", None):
                field_copy.column_name = f"{parent.prefix_column_name}{field_copy.column_name}"  # type: ignore
            else:
                # Otherwise, construct the new column_name based on the prefix and new_fieldname.
                field_copy.column_name = (
                    f"{parent.prefix_column_name}{new_fieldname[len(prefix) :]}"  # type: ignore
                )

        # Return the modified copy of the field.
        return field_copy

    def get_default_value(self) -> Any:
        """
        Retrieves the default Python value for a single-valued field.

        If the default is a callable, it is executed to get the value.

        Returns:
            The default value of the field, or `None` if no default is set.
        """
        # Get the default value, defaulting to None if not present.
        default = getattr(self, "default", None)
        # If the default is a callable, call it to get the actual value.
        if callable(default):
            return default()
        # Otherwise, return the default value directly.
        return default

    def get_default_values(self, field_name: str, cleaned_data: dict[str, Any]) -> dict[str, Any]:
        """
        Retrieves default values for the field, to be applied during data cleaning.

        For single-column fields, if the field name is not already present in
        `cleaned_data`, its default value is returned. Multi-value fields
        should override this method.

        Args:
            field_name: The name of the field.
            cleaned_data: The dictionary of already cleaned data.

        Returns:
            A dictionary containing the default value for the field if it's not
            already in `cleaned_data`, otherwise an empty dictionary.
        """
        # for multidefaults overwrite in subclasses get_default_values to
        # parse default values differently
        # NOTE: multi value fields should always check here if defaults were already applied
        # NOTE: when build meta fields without columns this should be empty
        # If the field_name is already in cleaned_data, no default is needed.
        if field_name in cleaned_data:
            return {}
        # Return a dictionary with the field's default value.
        return {field_name: self.get_default_value()}


class Field(BaseField):
    """
    Represents a single-column field in an Edgy data model.

    This class extends `BaseField` and provides concrete implementations for
    generating SQLAlchemy columns and handling data cleaning for single-column
    model attributes.
    """

    # For a single column field, auto_compute_server_default is by default None,
    # meaning it will defer to global settings.
    auto_compute_server_default: bool | None | Literal["ignore_null"] = None

    def check(self, value: Any) -> Any:
        """
        Performs validation or transformation on a single field value.

        This method is intended to be overridden by custom field types for
        specific validation logic. The base implementation simply returns the
        value unchanged.

        Args:
            value: The value of the field to be checked.

        Returns:
            The checked or transformed value.
        """
        return value

    def clean(self, name: str, value: Any, for_query: bool = False) -> dict[str, Any]:
        """
        Cleans and prepares a single field value for database interaction.

        This method applies the `check` method and wraps the result in a
        dictionary with the field's name as the key, making it suitable for
        database operations.

        Args:
            name: The name of the field.
            value: The value of the field to be cleaned.
            for_query: A boolean indicating if the cleaning is for a query context.

        Returns:
            A dictionary containing the cleaned field value.
        """
        return {name: self.check(value)}

    def get_column(self, name: str) -> sqlalchemy.Column | None:
        """
        Returns a single SQLAlchemy Column object corresponding to this field.

        This method constructs a `sqlalchemy.Column` instance based on the
        field's definition, including its type, constraints, nullability,
        and server default. Returns `None` for meta fields that do not map
        directly to a database column.

        Args:
            name: The name of the field, used as the default column name and key.

        Returns:
            A `sqlalchemy.Column` object or `None` if the field is a meta field.
        """
        # Validate the field against the ColumnDefinitionModel to extract column properties.
        column_model = ColumnDefinitionModel.model_validate(self, from_attributes=True)
        # If no column_type is defined, this is a meta field, so return None.
        if column_model.column_type is None:
            return None
        # Construct and return a SQLAlchemy Column.
        return sqlalchemy.Column(
            # Use column_model.column_name if present, otherwise use the field name.
            column_model.column_name or name,
            # Use the determined column type.
            column_model.column_type,
            # Unpack any additional constraints.
            *column_model.constraints,
            # Set the key for the column, typically the field name.
            key=name,
            # Determine nullability using the helper method.
            nullable=self.get_columns_nullable(),
            # Set the server default.
            server_default=self.get_server_default(),
            # Unpack other column arguments from the model, excluding None values.
            **column_model.model_dump(by_alias=True, exclude_none=True),
        )

    def get_columns(self, name: str) -> Sequence[sqlalchemy.Column]:
        """
        Returns a sequence containing the single SQLAlchemy Column for this field.

        This method calls `get_column` and wraps its result in a list, ensuring
        compatibility with methods expecting a sequence of columns.

        Args:
            name: The name of the field.

        Returns:
            A sequence containing the `sqlalchemy.Column` object, or an empty
            list if `get_column` returns `None`.
        """
        # Get the single column for the field.
        column = self.get_column(name)
        # If no column is returned (e.g., for meta fields), return an empty list.
        if column is None:
            return []
        # Otherwise, return a list containing the single column.
        return [column]


class BaseCompositeField(BaseField):
    """
    Base class for composite fields, which are composed of multiple sub-fields.

    Composite fields represent logical groupings of data that map to multiple
    database columns or properties. This class provides the foundational logic
    for handling such fields, including cleaning and converting values for
    database interaction and model representation.
    """

    def translate_name(self, name: str) -> str:
        """
        Translates a sub-field name for inner object representation or parsing.

        This method can be overridden by subclasses to provide specific naming
        conventions for composite sub-fields. The base implementation returns
        the name unchanged.

        Args:
            name: The original name of the sub-field.

        Returns:
            The translated name of the sub-field.
        """
        return name

    def get_composite_fields(self) -> dict[str, BaseFieldType]:
        """
        Abstract method that must be implemented by subclasses to return
        a dictionary of the sub-fields that compose this composite field.

        The keys of the dictionary should be the untranslated names of the
        sub-fields.

        Raises:
            NotImplementedError: This method must be implemented by subclasses.
        """
        raise NotImplementedError()

    @cached_property
    def composite_fields(self) -> dict[str, BaseFieldType]:
        """
        A cached property that returns the dictionary of composite sub-fields.

        The result of `get_composite_fields()` is cached after the first call
        for performance optimization.

        Returns:
            A dictionary where keys are untranslated sub-field names and values
            are `BaseFieldType` instances.
        """
        # Return the result of get_composite_fields(), which is cached.
        return self.get_composite_fields()

    def clean(self, field_name: str, value: Any, for_query: bool = False) -> dict[str, Any]:
        """
        Cleans and prepares the values of the composite field's sub-fields.

        This method iterates through the composite fields, extracts their values
        from the input `value` (which can be a dictionary or a model instance),
        and applies the `clean` method of each sub-field. It handles missing
        required sub-fields.

        Args:
            field_name: The full name of the composite field.
            value: The value of the composite field (e.g., a dictionary or model instance).
            for_query: A boolean indicating if the cleaning is for a query context.

        Returns:
            A dictionary containing the cleaned values of all sub-fields,
            prefixed appropriately.

        Raises:
            KeyError: If a required sub-field is missing when `value` is a dictionary.
            AttributeError: If a required sub-field is missing when `value` is an object.
        """
        # Calculate the prefix for sub-field names.
        prefix = field_name.removesuffix(self.name)
        result: dict[str, Any] = {}
        # Default error type for missing fields.
        ErrorType: type[Exception] = KeyError

        # If the value is None, return an empty dictionary as there's nothing to clean.
        if value is None:
            return result
        # If the value is not a dictionary, attempt to convert it to a dictionary
        # by accessing its __dict__ and set ErrorType to AttributeError.
        if not isinstance(value, dict):
            value = value.__dict__
            ErrorType = AttributeError

        # Iterate through each sub-field of the composite field.
        for sub_name, field in self.composite_fields.items():
            # Translate the sub-field name.
            translated_name = self.translate_name(sub_name)
            # If the translated sub-field name is not in the value.
            if translated_name not in value:
                # If the sub-field has a default or is not required, skip it.
                if field.has_default() or not field.is_required():
                    continue
                # Otherwise, raise an error for the missing required sub-field.
                raise ErrorType(f"Missing sub-field: {sub_name} for {field_name}")
            # Recursively call clean on the sub-field and update the result dictionary.
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
        Converts the raw value of the composite field into a format suitable
        for model instantiation.

        This method processes the values of sub-fields, potentially transforming
        them for the model's internal representation. It respects the current
        `CURRENT_PHASE` to determine strictness regarding missing fields.

        Args:
            field_name: The full name of the composite field.
            value: The raw value of the composite field (e.g., from database result).

        Returns:
            A dictionary containing the transformed values of all sub-fields.

        Raises:
            KeyError: If a required sub-field is missing when `value` is a dictionary
                      and the phase is not 'init' or 'init_db'.
            AttributeError: If a required sub-field is missing when `value` is an object
                            and the phase is not 'init' or 'init_db'.
        """
        result = {}
        # Get the current phase from the context.
        phase = CURRENT_PHASE.get()
        # Default error type for missing fields.
        ErrorType: type[Exception] = KeyError
        # If the value is not a dictionary, attempt to convert it to a dictionary
        # by accessing its __dict__ and set ErrorType to AttributeError.
        if not isinstance(value, dict):
            value = value.__dict__
            ErrorType = AttributeError
        # Iterate through each sub-field of the composite field.
        for sub_name, field in self.composite_fields.items():
            # Translate the sub-field name.
            translated_name = self.translate_name(sub_name)
            # If the translated sub-field name is not in the value.
            if translated_name not in value:
                # If the current phase is 'init' or 'init_db', continue without error.
                if phase == "init" or phase == "init_db":
                    continue
                # Otherwise, raise an error for the missing sub-field.
                raise ErrorType(f"Missing sub-field: {sub_name} for {field_name}")
            # Recursively call to_model on the sub-field and update the result dictionary.
            result.update(field.to_model(sub_name, value.get(translated_name, None)))
        return result

    def get_default_values(self, field_name: str, cleaned_data: dict[str, Any]) -> Any:
        """
        Retrieves default values for the composite field.

        For composite fields, this base implementation returns an empty dictionary.
        Subclasses might override this to provide specific default logic.

        Args:
            field_name: The name of the composite field.
            cleaned_data: The dictionary of already cleaned data.

        Returns:
            An empty dictionary, as composite fields typically manage defaults
            at the sub-field level.
        """
        return {}


class RelationshipField(BaseField):
    """
    Base class for all relationship fields (e.g., Foreign Key, Many-to-Many).

    This class provides common attributes and abstract methods expected of
    fields that define relationships between models, such as traversing
    relationships and checking cross-database connections.
    """

    def traverse_field(self, path: str) -> tuple[Any, str, str]:
        """
        Abstract method to traverse a relationship path.

        Args:
            path: The path string to traverse (e.g., "related_model__field").

        Raises:
            NotImplementedError: This method must be implemented by subclasses.
        """
        raise NotImplementedError()

    def is_cross_db(self, owner_database: Database | None = None) -> bool:
        """
        Abstract method to determine if the relationship spans across different databases.

        Args:
            owner_database: The database instance of the owning model.

        Raises:
            NotImplementedError: This method must be implemented by subclasses.
        """
        raise NotImplementedError()

    def get_related_model_for_admin(self) -> type[BaseModelType] | None:
        """
        Abstract method to retrieve the related model if it's registered for admin.

        Returns:
            The related model class if it's an admin model, otherwise `None`.

        Raises:
            NotImplementedError: This method must be implemented by subclasses.
        """
        raise NotImplementedError()

    @abstractmethod
    def reverse_clean(self, name: str, value: Any, for_query: bool = False) -> dict[str, Any]:
        """
        Abstract method for cleaning values in a reverse relationship context.

        Args:
            name: The name of the field in the reverse relationship.
            value: The value to clean.
            for_query: A boolean indicating if the cleaning is for a query context.

        Returns:
            A dictionary containing the cleaned value for the reverse relationship.

        Raises:
            NotImplementedError: This method must be implemented by subclasses.
        """
        ...

    def expand_relationship(self, value: Any) -> Any:
        """
        Expands the relationship value.

        This method can be overridden by subclasses to return the actual related
        object or a specific representation of the relationship. The base
        implementation simply returns the value as is.

        Args:
            value: The raw value of the relationship.

        Returns:
            The expanded relationship value.
        """
        return value

    def to_model(
        self,
        field_name: str,
        value: Any,
    ) -> dict[str, Any]:
        """
        Converts the raw relationship value into a format suitable for model instantiation.

        This method uses `expand_relationship` to transform the value before
        including it in the dictionary.

        Args:
            field_name: The name of the relationship field.
            value: The raw value of the relationship.

        Returns:
            A dictionary containing the transformed relationship value.
        """
        return {field_name: self.expand_relationship(value)}


class PKField(BaseCompositeField):
    """
    Represents a primary key field, which can be a single column or composite.

    This specialized composite field manages the primary key(s) of a model,
    providing mechanisms for retrieval, modification, and validation of primary
    key values. It automatically handles single-column primary keys versus
    multi-column (composite) primary keys.
    """

    def __init__(self, **kwargs: Any) -> None:
        """
        Initializes the PKField.

        Sets the default value to `None`, the field type and annotation to `Any`,
        and adds Pydantic metadata to skip validation and schema generation
        for this internal field.

        Args:
            **kwargs: Additional keyword arguments passed to the `BaseField` constructor.
        """
        kwargs["default"] = None
        kwargs["field_type"] = kwargs["annotation"] = Any
        super().__init__(**kwargs)
        # Add metadata to skip Pydantic validation for this field.
        self.metadata.append(SkipValidation())
        # Add metadata to prevent Pydantic from generating a JSON schema for this field.
        self.metadata.append(WithJsonSchema(mode="validation", json_schema=None))

    def __get__(self, instance: BaseModelType, owner: Any = None) -> dict[str, Any] | Any:
        """
        Descriptor method to retrieve the primary key value(s) from a model instance.

        If the primary key is single-column, it returns the value directly.
        For composite primary keys, it returns a dictionary mapping primary
        key names to their values. It temporarily modifies `MODEL_GETATTR_BEHAVIOR`
        to prevent unnecessary loads.

        Args:
            instance: The model instance from which to get the primary key.
            owner: The owner class (not typically used for instance access).

        Returns:
            The primary key value (for single PK) or a dictionary of primary
            key values (for composite PK).
        """
        # Get primary key column names and field names from the owner model.
        pkcolumns = self.owner.pkcolumns
        pknames = self.owner.pknames
        # Ensure there is at least one primary key column.
        assert len(pkcolumns) >= 1
        # Temporarily set MODEL_GETATTR_BEHAVIOR to "passdown" to avoid triggering
        # unnecessary loads during PK retrieval.
        token = MODEL_GETATTR_BEHAVIOR.set("passdown")
        try:
            # If there's only one primary key field, return its value directly.
            if len(pknames) == 1:
                return getattr(instance, pknames[0], None)
            # For composite primary keys, build a dictionary of PK values.
            d = {}
            for key in pknames:
                # Get the translated name for the key.
                translated_name = self.translate_name(key)
                # Get the field object for the primary key.
                field = instance.meta.fields.get(key)
                # If the field exists and has a __get__ method, use it; otherwise, use getattr.
                if field and hasattr(field, "__get__"):
                    d[translated_name] = field.__get__(instance, owner)
                else:
                    d[translated_name] = getattr(instance, key, None)
            # Include any fieldless primary key columns.
            for key in self.fieldless_pkcolumns:
                translated_name = self.translate_name(key)
                d[translated_name] = getattr(instance, key, None)
        finally:
            # Reset MODEL_GETATTR_BEHAVIOR to its previous state.
            MODEL_GETATTR_BEHAVIOR.reset(token)
        return d

    def modify_input(self, name: str, kwargs: dict[str, Any]) -> None:
        """
        Modifies input keyword arguments, typically for model creation or updates.

        This method checks for potential collisions where both the `pk` field
        and individual primary key fields are provided in the input, raising an
        error if such a collision occurs.

        Args:
            name: The name of the primary key field.
            kwargs: The dictionary of keyword arguments provided to the model.

        Raises:
            ValueError: If both the primary key field and individual primary
                        key components are specified.
        """
        # If the PK field name is not in kwargs, do nothing.
        if name not in kwargs:
            return
        # Check for collisions with individual primary key names.
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
        """
        Prevents embedding of the primary key field.

        Primary key fields are typically not meant to be embedded within other
        composite fields directly. This method always returns `None` to indicate
        that embedding is not supported for PKField.

        Args:
            prefix: The prefix to be added (ignored).
            new_fieldname: The new field name (ignored).
            owner: The new owner model class (ignored).
            parent: The parent field (ignored).

        Returns:
            `None`, indicating that this field cannot be embedded.
        """
        return None

    def clean(self, field_name: str, value: Any, for_query: bool = False) -> dict[str, Any]:
        """
        Cleans and prepares the primary key value(s) for database interaction.

        This method handles both single-column and composite primary keys.
        For single-column PKs, it delegates to the individual PK field's `clean` method.
        For composite PKs, it ensures all components are present and cleaned.
        It also handles fieldless primary key columns.

        Args:
            field_name: The name of the primary key field.
            value: The raw primary key value(s).
            for_query: A boolean indicating if the cleaning is for a query context.

        Returns:
            A dictionary containing the cleaned primary key value(s).

        Raises:
            ValueError: If a required primary key component is missing, especially
                        in a query context for incomplete PK definitions.
        """
        # Get primary key columns and names from the owner.
        pkcolumns = self.owner.pkcolumns
        pknames = self.owner.pknames
        # Calculate the prefix for sub-field names.
        prefix = field_name.removesuffix(self.name)
        # Ensure there is at least one primary key column.
        assert len(pkcolumns) >= 1
        # If there's a single primary key and it's not incomplete, and the value
        # is not a dict or BaseModel, delegate to the single PK field's clean method.
        if (
            len(pknames) == 1
            and not self.is_incomplete
            and not isinstance(value, dict | BaseModel)
        ):
            pkname = pknames[0]
            field = self.owner.meta.fields[pkname]
            return field.clean(f"{prefix}{pkname}", value, for_query=for_query)
        # For composite or incomplete PKs, call the parent's clean method.
        retdict = super().clean(field_name, value, for_query=for_query)
        # If the PK is incompletely defined (has fieldless columns), process them.
        if self.is_incomplete:
            if isinstance(value, dict):
                for column_name in self.fieldless_pkcolumns:
                    translated_name = self.translate_name(column_name)
                    if translated_name not in value:
                        # If for_query and missing, raise error.
                        if not for_query:
                            continue
                        raise ValueError(f"Missing key: {translated_name} for {field_name}")
                    retdict[f"{prefix}{column_name}"] = value[translated_name]
            else:
                for column_name in self.fieldless_pkcolumns:
                    translated_name = self.translate_name(column_name)
                    if not hasattr(value, translated_name):
                        # If for_query and missing, raise error.
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
        """
        Converts the raw primary key value(s) into a format suitable for model instantiation.

        This method handles single-column primary keys by delegating to the
        individual PK field's `to_model` method. For composite keys, it uses
        the base composite field's `to_model` method.

        Args:
            field_name: The name of the primary key field.
            value: The raw primary key value(s).

        Returns:
            A dictionary containing the transformed primary key value(s).

        Raises:
            ValueError: If an incomplete primary key definition is encountered.
        """
        # Get primary key names from the owner.
        pknames = self.owner.pknames
        # Ensure there is at least one primary key column.
        assert len(self.owner.pkcolumns) >= 1
        # If the PK is incomplete, raise an error as it cannot be set.
        if self.is_incomplete:
            raise ValueError("Cannot set an incomplete defined pk!")
        # If there's a single primary key and the value is not a dict or BaseModel,
        # delegate to the single PK field's to_model method.
        if len(pknames) == 1 and not isinstance(value, dict | BaseModel):
            field = self.owner.meta.fields[pknames[0]]
            return field.to_model(pknames[0], value)
        # For composite PKs, call the parent's to_model method.
        return super().to_model(field_name, value)

    def get_composite_fields(self) -> dict[str, BaseFieldType]:
        """
        Returns a dictionary of the fields that constitute this primary key.

        This method identifies the fields corresponding to the primary key
        names of the owner model.

        Returns:
            A dictionary where keys are primary key field names and values
            are their corresponding `BaseFieldType` instances.
        """
        # Return a dictionary mapping primary key names to their corresponding field objects.
        return {field: self.owner.meta.fields[field] for field in self.owner.pknames}

    @cached_property
    def fieldless_pkcolumns(self) -> frozenset[str]:
        """
        A cached property that returns a frozenset of primary key column names
        that do not have corresponding field definitions.

        These are typically columns that are part of a composite primary key
        but are not directly mapped to a Python model field.

        Returns:
            A frozenset of primary key column names without corresponding fields.
        """
        field_less = set()
        # Iterate through primary key column names.
        for colname in self.owner.pkcolumns:
            # If a column name is not in the model's columns_to_field mapping, add it to field_less.
            if colname not in self.owner.meta.columns_to_field:
                field_less.add(colname)
        # Return the set as a frozenset.
        return frozenset(field_less)

    @property
    def is_incomplete(self) -> bool:
        """
        Checks if the primary key definition is incomplete.

        A primary key is considered incomplete if it contains `fieldless_pkcolumns`.

        Returns:
            `True` if the primary key definition is incomplete, `False` otherwise.
        """
        # Returns True if there are any fieldless primary key columns.
        return bool(self.fieldless_pkcolumns)

    def is_required(self) -> bool:
        """
        Indicates that a primary key field is never "required" in the typical sense,
        as its value is often generated automatically (e.g., autoincrementing) or
        derived from other fields.

        Returns:
            `False`, as primary key fields are not considered required inputs.
        """
        return False


class BaseForeignKey(RelationshipField):
    """
    Base class for foreign key relationships.

    This class provides the fundamental logic for defining and managing
    many-to-one relationships, including handling related model resolution,
    cross-database checks, and reverse relationship naming.
    """

    is_m2m: bool = False
    related_name: str | Literal[False] = ""
    # Name used for backward relations. Only useful if related_name = False,
    # because otherwise it gets overwritten.
    reverse_name: str = ""

    @property
    def target_registry(self) -> Registry:
        """
        Retrieves the target registry for resolving the related model.

        If `to` is a string (lazy reference to a model), this registry is used
        to look up the actual model class. It prioritizes the owner's registry,
        falls back to a global `FALLBACK_TARGET_REGISTRY`, and raises an error
        if no registry can be found.

        Returns:
            The `Registry` instance used to resolve the target model.

        Raises:
            AssertionError: If no target registry can be determined.
        """
        # Check if _target_registry attribute is already set.
        if not hasattr(self, "_target_registry"):
            target_registry: Registry | None | Literal[False] = self.owner.meta.registry
            # If the owner model doesn't have a registry (e.g., for abstract models),
            # try to get it from the global FALLBACK_TARGET_REGISTRY.
            if target_registry is None:
                target_registry = FALLBACK_TARGET_REGISTRY.get()
            # Assert that a target registry has been found.
            assert target_registry, (
                f"{self.owner} ({self.name}): no registry found, "
                "nor FALLBACK_TARGET_REGISTRY found, nor 'target_registry' set"
            )
            return target_registry
        # If _target_registry is set, return it.
        return cast("Registry", self._target_registry)

    @target_registry.setter
    def target_registry(self, value: Any) -> None:
        """
        Sets the target registry for the foreign key.

        Args:
            value: The `Registry` instance to set as the target registry.
        """
        self._target_registry = value

    @target_registry.deleter
    def target_registry(self) -> None:
        """
        Deletes the cached target registry, forcing re-evaluation on next access.
        """
        # Suppress AttributeError if _target_registry doesn't exist.
        with contextlib.suppress(AttributeError):
            delattr(self, "_target_registry")

    @property
    def target(self) -> Any:
        """
        Retrieves the target model class for the foreign key relationship.

        If `self.to` is a string (a lazy reference), it resolves the actual
        model class using `target_registry`. The resolved target model is cached.

        Returns:
            The target model class.
        """
        # Check if _target attribute is already set.
        if not hasattr(self, "_target"):
            # If 'to' is a string, resolve the model from the target registry.
            if isinstance(self.to, str):
                self._target = self.target_registry.get_model(self.to)
            else:
                # Otherwise, 'to' is already the target model.
                self._target = self.to
        # Return the resolved target model.
        return self._target

    @target.setter
    def target(self, value: Any) -> None:
        """
        Sets the target model for the foreign key and clears the cached target.

        Args:
            value: The target model class to set.
        """
        # Suppress AttributeError if _target doesn't exist and delete it.
        with contextlib.suppress(AttributeError):
            delattr(self, "_target")
        # Set the 'to' attribute to the new value.
        self.to = value

    @target.deleter
    def target(self) -> None:
        """
        Deletes the cached target model, forcing re-query on next access.
        """
        # Clear the cache for _target.
        with contextlib.suppress(AttributeError):
            delattr(self, "_target")

    def is_cross_db(self, owner_database: Database | None = None) -> bool:
        """
        Checks if the foreign key relationship spans across different databases.

        Compares the URL of the owning model's database with the URL of the
        target model's database.

        Args:
            owner_database: The database instance of the owning model. If `None`,
                            it defaults to `self.owner.database`.

        Returns:
            `True` if the relationship is cross-database, `False` otherwise.
        """
        # Use the provided owner_database or default to the owner model's database.
        if owner_database is None:
            owner_database = self.owner.database
        # Compare the string representation of the database URLs.
        return str(owner_database.url) != str(self.target.database.url)

    def get_related_model_for_admin(self) -> type[BaseModelType] | None:
        """
        Retrieves the related model if it is registered as an admin model.

        This is used, for example, by admin interfaces to determine if a related
        object can be managed.

        Returns:
            The related model class if it's an admin model, otherwise `None`.
        """
        # Check if the target model's name is present in the target registry's admin models.
        if self.target.__name__ in self.target_registry.admin_models:
            # If it is, cast and return the target model type.
            return cast("type[BaseModelType]", self.target)
        return None

    @abstractmethod
    def reverse_clean(self, name: str, value: Any, for_query: bool = False) -> dict[str, Any]:
        """
        Abstract method for cleaning values in a reverse relationship context.

        This method must be implemented by concrete foreign key classes to
        handle how related model data is processed when coming from the "other side"
        of the relationship (e.g., when saving a related object that points back).

        Args:
            name: The name of the field in the reverse relationship.
            value: The value to clean.
            for_query: A boolean indicating if the cleaning is for a query context.

        Returns:
            A dictionary containing the cleaned value for the reverse relationship.
        """
        ...

    def expand_relationship(self, value: Any) -> Any:
        """
        Expands the relationship value.

        This method can be overridden by subclasses to return the actual related
        object or a specific representation of the relationship. The base
        implementation simply returns the value as is.

        Args:
            value: The raw value of the relationship.

        Returns:
            The expanded relationship value.
        """
        return value

    def to_model(
        self,
        field_name: str,
        value: Any,
    ) -> dict[str, Any]:
        """
        Converts the raw relationship value into a format suitable for model instantiation.

        This method uses `expand_relationship` to transform the value before
        including it in the dictionary.

        Args:
            field_name: The name of the relationship field.
            value: The raw value of the relationship.

        Returns:
            A dictionary containing the transformed relationship value.
        """
        return {field_name: self.expand_relationship(value)}
