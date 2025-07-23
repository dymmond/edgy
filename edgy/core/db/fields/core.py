from __future__ import annotations

import copy
import datetime
import decimal
import enum
import ipaddress
import uuid
import warnings
from collections.abc import Callable
from enum import Enum, EnumMeta
from re import Pattern
from secrets import compare_digest
from typing import TYPE_CHECKING, Annotated, Any, cast

import orjson
import pydantic
import sqlalchemy
from monkay import Monkay
from pydantic.networks import AnyUrl, EmailStr, IPvAnyAddress
from sqlalchemy.dialects import oracle, postgresql

from edgy.core.db.context_vars import CURRENT_PHASE
from edgy.core.db.fields._internal import IPAddress
from edgy.core.db.fields.base import Field
from edgy.core.db.fields.factories import FieldFactory
from edgy.core.db.fields.types import BaseFieldType
from edgy.exceptions import FieldDefinitionError

from .mixins import AutoNowMixin as _AutoNowMixin
from .mixins import IncrementOnSaveBaseField, TimezonedField
from .place_holder_field import PlaceholderField as _PlaceholderField

if TYPE_CHECKING:
    import zoneinfo

CLASS_DEFAULTS = ["cls", "__class__", "kwargs"]


class CharField(FieldFactory, str):
    field_type = str

    def __new__(
        cls,
        *,
        min_length: int | None = None,
        regex: str | Pattern = None,
        pattern: str | Pattern = None,
        **kwargs: Any,
    ) -> BaseFieldType:
        """
        Initializes a new CharField instance.

        This method sets up a string field with optional length constraints and
        regular expression validation. It ensures that 'pattern' is used if
        'regex' is provided, and then constructs the field with all relevant
        parameters.
        """
        if pattern is None:
            pattern = regex
        del regex
        kwargs = {
            **kwargs,
            **{key: value for key, value in locals().items() if key not in CLASS_DEFAULTS},
        }

        return super().__new__(cls, **kwargs)

    @classmethod
    def validate(cls, kwargs: dict[str, Any]) -> None:
        """
        Validates the keyword arguments for a CharField.

        Ensures that 'max_length' is a positive integer if provided, and
        validates the types of 'min_length', 'max_length', and 'pattern'/'regex'.
        """
        max_length = kwargs.get("max_length", 0)
        if max_length is not None and max_length <= 0:
            raise FieldDefinitionError(detail=f"'max_length' is required for {cls.__name__}")

        min_length = kwargs.get("min_length")
        pattern = kwargs.get("regex")

        # Type assertions for min_length, max_length, and pattern
        assert min_length is None or isinstance(min_length, int)
        assert max_length is None or isinstance(max_length, int)
        assert pattern is None or isinstance(pattern, str | Pattern)

    @classmethod
    def get_column_type(cls, kwargs: dict[str, Any]) -> Any:
        """
        Determines the SQLAlchemy column type based on field arguments.

        If `max_length` is not provided, it defaults to `sqlalchemy.Text`,
        otherwise, it uses `sqlalchemy.String` with the specified length.
        Collation can also be applied.
        """
        max_length: int | None = kwargs.get("max_length")
        return (
            sqlalchemy.Text(collation=kwargs.get("collation"))
            if max_length is None
            else sqlalchemy.String(length=max_length, collation=kwargs.get("collation"))
        )

    @classmethod
    def operator_to_clause(
        cls,
        field_obj: BaseFieldType,
        field_name: str,
        operator: str,
        table: sqlalchemy.Table,
        value: Any,
        original_fn: Any,
    ) -> Any:
        """
        Overwrite for isempty.

        Args:
            field_name: The name of the column to apply the operator to.
            operator: The operation code (e.g., 'iexact', 'contains', 'isnull').
            table: The SQLAlchemy Table object the column belongs to.
            value: The value to compare against.
            original_fn: The field object original function.

        Returns:
            A SQLAlchemy clause suitable for use in a query's WHERE statement.

        Raises:
            KeyError: If 'field_name' does not correspond to an existing column in the table.
            AttributeError: If the mapped operator does not exist as a method on the column.
        """
        mapped_operator = field_obj.operator_mapping.get(operator, operator)
        if mapped_operator == "isempty":
            column = table.columns[field_name]
            is_empty = sqlalchemy.or_(column.is_(None), column == "")
            return is_empty if value else sqlalchemy.not_(is_empty)
        else:
            return original_fn(field_name, operator, table, value)


class TextField(CharField):
    """
    Represents a text field, which is a CharField without a required maximum length.
    """

    @classmethod
    def validate(cls, kwargs: dict[str, Any]) -> None:
        """
        Validates the keyword arguments for a TextField.

        Sets a default `max_length` of `None` for text fields,
        then calls the parent `CharField` validation.
        """
        kwargs.setdefault("max_length", None)
        super().validate(kwargs)


class IntegerField(FieldFactory, int):
    """
    Represents an integer field.

    This field supports various integer constraints like greater than,
    less than, and multiple of. It also handles auto-incrementing behavior
    for primary keys.
    """

    field_type = int
    field_bases = (IncrementOnSaveBaseField,)

    def __new__(
        cls,
        *,
        ge: int | float | decimal.Decimal | None = None,
        gt: int | float | decimal.Decimal | None = None,
        le: int | float | decimal.Decimal | None = None,
        lt: int | float | decimal.Decimal | None = None,
        multiple_of: int | None = None,
        increment_on_save: int = 0,
        **kwargs: Any,
    ) -> BaseFieldType:
        """
        Initializes a new IntegerField instance.

        Sets up an integer field with optional range constraints,
        multiplicity, and increment-on-save functionality.
        """
        kwargs = {
            **kwargs,
            **{k: v for k, v in locals().items() if k not in CLASS_DEFAULTS},
        }
        return super().__new__(cls, **kwargs)

    @classmethod
    def get_column_type(cls, kwargs: dict[str, Any]) -> Any:
        """
        Returns the SQLAlchemy column type for an IntegerField.
        """
        return sqlalchemy.Integer()

    @classmethod
    def validate(cls, kwargs: dict[str, Any]) -> None:
        """
        Validates the keyword arguments for an IntegerField.

        Handles `autoincrement` deprecation warning and ensures
        `increment_on_save` is not used with `autoincrement` or `null`.
        """
        increment_on_save = kwargs.get("increment_on_save", 0)
        # Check for autoincrement deprecation when primary_key is True and autoincrement is not set
        if (
            increment_on_save == 0
            and kwargs.get("primary_key", False)
            and "autoincrement" not in kwargs
        ):
            warnings.warn(
                (
                    "Not setting autoincrement on an Integer field with `primary_key=True` is "
                    "deprecated. We change the default to False in future."
                ),
                DeprecationWarning,
                stacklevel=4,
            )
            kwargs["autoincrement"] = True
        # Raise error if increment_on_save is incompatible with autoincrement or null
        if increment_on_save != 0:
            if kwargs.get("autoincrement"):
                raise FieldDefinitionError(
                    detail="'autoincrement' is incompatible with 'increment_on_save'"
                )
            if kwargs.get("null"):
                raise FieldDefinitionError(
                    detail="'null' is incompatible with 'increment_on_save'"
                )
            kwargs.setdefault("read_only", True)
            kwargs["inject_default_on_partial_update"] = True

    @classmethod
    def operator_to_clause(
        cls,
        field_obj: BaseFieldType,
        field_name: str,
        operator: str,
        table: sqlalchemy.Table,
        value: Any,
        original_fn: Any,
    ) -> Any:
        """
        Overwrite for isempty.

        Args:
            field_name: The name of the column to apply the operator to.
            operator: The operation code (e.g., 'iexact', 'contains', 'isnull').
            table: The SQLAlchemy Table object the column belongs to.
            value: The value to compare against.
            original_fn: The field object original function.

        Returns:
            A SQLAlchemy clause suitable for use in a query's WHERE statement.

        Raises:
            KeyError: If 'field_name' does not correspond to an existing column in the table.
            AttributeError: If the mapped operator does not exist as a method on the column.
        """
        mapped_operator = field_obj.operator_mapping.get(operator, operator)
        if mapped_operator == "isempty":
            column = table.columns[field_name]
            is_empty = sqlalchemy.or_(column.is_(None), column == 0)
            return is_empty if value else sqlalchemy.not_(is_empty)
        else:
            return original_fn(field_name, operator, table, value)


class FloatField(FieldFactory, float):
    """
    Represents a floating-point number field.

    This field supports precision and range constraints for float values.
    """

    field_type = float

    def __new__(
        cls,
        *,
        max_digits: int | None = None,
        ge: int | float | decimal.Decimal | None = None,
        gt: int | float | decimal.Decimal | None = None,
        le: int | float | decimal.Decimal | None = None,
        lt: int | float | decimal.Decimal | None = None,
        **kwargs: Any,
    ) -> BaseFieldType:
        """
        Initializes a new FloatField instance.

        Handles the `max_digits` argument by renaming it to `precision`
        for internal consistency with Pydantic, and sets up the field
        with optional range constraints.
        """
        # Pydantic doesn't support max_digits for float, so rename it to precision.
        if max_digits is not None:
            kwargs.setdefault("precision", max_digits)
        del max_digits
        kwargs = {
            **kwargs,
            **{key: value for key, value in locals().items() if key not in CLASS_DEFAULTS},
        }
        return super().__new__(cls, **kwargs)

    @classmethod
    def get_column_type(cls, kwargs: dict[str, Any]) -> Any:
        """
        Returns the SQLAlchemy column type for a FloatField.

        Applies precision if specified, and provides a special variant
        for Oracle databases to handle binary precision.
        """
        precision: int | None = kwargs.get("precision")
        if precision is None:
            return sqlalchemy.Float(asdecimal=False)
        return sqlalchemy.Float(precision=precision, asdecimal=False).with_variant(
            # Type ignore because oracle.FLOAT is a specific dialect type.
            oracle.FLOAT(binary_precision=round(precision / 0.30103), asdecimal=False),  # type: ignore
            "oracle",
        )

    @classmethod
    def operator_to_clause(
        cls,
        field_obj: BaseFieldType,
        field_name: str,
        operator: str,
        table: sqlalchemy.Table,
        value: Any,
        original_fn: Any,
    ) -> Any:
        """
        Overwrite for isempty.

        Args:
            field_name: The name of the column to apply the operator to.
            operator: The operation code (e.g., 'iexact', 'contains', 'isnull').
            table: The SQLAlchemy Table object the column belongs to.
            value: The value to compare against.
            original_fn: The field object original function.

        Returns:
            A SQLAlchemy clause suitable for use in a query's WHERE statement.

        Raises:
            KeyError: If 'field_name' does not correspond to an existing column in the table.
            AttributeError: If the mapped operator does not exist as a method on the column.
        """
        mapped_operator = field_obj.operator_mapping.get(operator, operator)
        if mapped_operator == "isempty":
            column = table.columns[field_name]
            is_empty = sqlalchemy.or_(column.is_(None), column == 0.0)
            return is_empty if value else sqlalchemy.not_(is_empty)
        else:
            return original_fn(field_name, operator, table, value)


class BigIntegerField(IntegerField):
    """
    Represents a big integer field, inheriting from IntegerField.
    """

    @classmethod
    def validate(cls, kwargs: dict[str, Any]) -> None:
        """
        Validates the keyword arguments for a BigIntegerField.

        Ensures that `skip_reflection_type_check` is set if
        `autoincrement` is enabled.
        """
        super().validate(kwargs)
        if kwargs.get("autoincrement", False):
            kwargs.setdefault("skip_reflection_type_check", True)

    @classmethod
    def get_column_type(cls, kwargs: dict[str, Any]) -> Any:
        """
        Returns the SQLAlchemy column type for a BigIntegerField.

        Provides a specific variant for SQLite to handle big integers
        as regular integers when `autoincrement` is used.
        """
        # Sqlite special case: cannot have a big IntegerField as PK with autoincrement.
        if kwargs.get("autoincrement"):
            return sqlalchemy.BigInteger().with_variant(sqlalchemy.Integer, "sqlite")
        return sqlalchemy.BigInteger()


class SmallIntegerField(IntegerField):
    """
    Represents a small integer field, inheriting from IntegerField.
    """

    @classmethod
    def get_column_type(cls, kwargs: dict[str, Any]) -> Any:
        """
        Returns the SQLAlchemy column type for a SmallIntegerField.
        """
        return sqlalchemy.SmallInteger()


class DecimalField(FieldFactory, decimal.Decimal):
    """
    Represents a decimal number field.

    This field supports specific precision and scale for decimal values.
    """

    field_type = decimal.Decimal

    def __new__(
        cls,
        *,
        ge: int | float | decimal.Decimal | None = None,
        gt: int | float | decimal.Decimal | None = None,
        le: int | float | decimal.Decimal | None = None,
        lt: int | float | decimal.Decimal | None = None,
        multiple_of: int | decimal.Decimal | None = None,
        max_digits: int | None = None,
        decimal_places: int | None = None,
        **kwargs: Any,
    ) -> BaseFieldType:
        """
        Initializes a new DecimalField instance.

        Sets up a decimal field with optional range constraints, multiplicity,
        maximum digits, and decimal places.
        """
        kwargs = {
            **kwargs,
            **{k: v for k, v in locals().items() if k not in CLASS_DEFAULTS},
        }
        return super().__new__(cls, **kwargs)

    @classmethod
    def get_column_type(cls, kwargs: dict[str, Any]) -> Any:
        """
        Returns the SQLAlchemy column type for a DecimalField.

        Uses `sqlalchemy.Numeric` with specified precision (max_digits)
        and scale (decimal_places).
        """
        return sqlalchemy.Numeric(
            precision=kwargs.get("max_digits"), scale=kwargs.get("decimal_places"), asdecimal=True
        )

    @classmethod
    def validate(cls, kwargs: dict[str, Any]) -> None:
        """
        Validates the keyword arguments for a DecimalField.

        Ensures that 'decimal_places' is provided and is not negative.
        """
        super().validate(kwargs)

        decimal_places = kwargs.get("decimal_places")
        if decimal_places is None or decimal_places < 0:
            raise FieldDefinitionError("decimal_places are required for DecimalField")

    @classmethod
    def operator_to_clause(
        cls,
        field_obj: BaseFieldType,
        field_name: str,
        operator: str,
        table: sqlalchemy.Table,
        value: Any,
        original_fn: Any,
    ) -> Any:
        """
        Overwrite for isempty.

        Args:
            field_name: The name of the column to apply the operator to.
            operator: The operation code (e.g., 'iexact', 'contains', 'isnull').
            table: The SQLAlchemy Table object the column belongs to.
            value: The value to compare against.
            original_fn: The field object original function.

        Returns:
            A SQLAlchemy clause suitable for use in a query's WHERE statement.

        Raises:
            KeyError: If 'field_name' does not correspond to an existing column in the table.
            AttributeError: If the mapped operator does not exist as a method on the column.
        """
        mapped_operator = field_obj.operator_mapping.get(operator, operator)
        if mapped_operator == "isempty":
            column = table.columns[field_name]
            is_empty = sqlalchemy.or_(column.is_(None), column == decimal.Decimal("0"))
            return is_empty if value else sqlalchemy.not_(is_empty)
        else:
            return original_fn(field_name, operator, table, value)


# in python it is not possible to subclass bool. So only use bool for type checking.
class BooleanField(FieldFactory, cast(bool, int)):
    """
    Represents a boolean field.

    Note: Due to Python's limitations, `bool` cannot be directly subclassed,
    hence the `cast(bool, int)` for type checking purposes.
    """

    field_type = bool

    @classmethod
    def get_column_type(cls, kwargs: dict[str, Any]) -> Any:
        """
        Returns the SQLAlchemy column type for a BooleanField.
        """
        return sqlalchemy.Boolean()

    @classmethod
    def operator_to_clause(
        cls,
        field_obj: BaseFieldType,
        field_name: str,
        operator: str,
        table: sqlalchemy.Table,
        value: Any,
        original_fn: Any,
    ) -> Any:
        """
        Overwrite for isempty.

        Args:
            field_name: The name of the column to apply the operator to.
            operator: The operation code (e.g., 'iexact', 'contains', 'isnull').
            table: The SQLAlchemy Table object the column belongs to.
            value: The value to compare against.
            original_fn: The field object original function.

        Returns:
            A SQLAlchemy clause suitable for use in a query's WHERE statement.

        Raises:
            KeyError: If 'field_name' does not correspond to an existing column in the table.
            AttributeError: If the mapped operator does not exist as a method on the column.
        """
        mapped_operator = field_obj.operator_mapping.get(operator, operator)
        if mapped_operator == "isempty":
            column = table.columns[field_name]
            is_empty = sqlalchemy.or_(column.is_(None), column.is_(False))
            return is_empty if value else sqlalchemy.not_(is_empty)
        else:
            return original_fn(field_name, operator, table, value)


class DateTimeField(_AutoNowMixin, datetime.datetime):
    """
    Represents a datetime field.

    This field supports auto-now and auto-now-add functionalities,
    as well as timezone handling.
    """

    field_type = datetime.datetime
    field_bases = (TimezonedField, Field)

    def __new__(
        cls,
        *,
        auto_now: bool | None = False,
        auto_now_add: bool | None = False,
        default_timezone: zoneinfo.ZoneInfo | None = None,
        force_timezone: zoneinfo.ZoneInfo | None = None,
        remove_timezone: bool = False,
        **kwargs: Any,
    ) -> BaseFieldType:
        """
        Initializes a new DateTimeField instance.

        Configures auto-now, auto-now-add, and timezone settings.
        `with_timezone` is determined by `remove_timezone`.
        """
        kwargs = {
            **kwargs,
            **{k: v for k, v in locals().items() if k not in CLASS_DEFAULTS},
        }
        kwargs.setdefault("with_timezone", not remove_timezone)
        return super().__new__(cls, **kwargs)

    @classmethod
    def get_column_type(cls, kwargs: dict[str, Any]) -> Any:
        """
        Returns the SQLAlchemy column type for a DateTimeField.

        The column type is `sqlalchemy.DateTime`, with timezone support
        determined by the `with_timezone` argument.
        """
        with_timezone: bool = kwargs.get("with_timezone", True)
        return sqlalchemy.DateTime(with_timezone)

    @classmethod
    def get_default_values(
        cls,
        field_obj: Field,
        field_name: str,
        cleaned_data: dict[str, Any],
        original_fn: Any = None,
    ) -> Any:
        """
        Retrieves default values for the DateTimeField.

        Handles `auto_now_add` behavior, ensuring it only applies during
        initial creation and not on updates.
        """
        phase = CURRENT_PHASE.get()
        if field_obj.auto_now_add and phase == "prepare_update":
            return {}
        return original_fn(field_name, cleaned_data)


class DateField(_AutoNowMixin, datetime.date):
    """
    Represents a date field.

    This field supports auto-now and auto-now-add functionalities for dates.
    """

    field_type = datetime.date
    field_bases = (TimezonedField, Field)

    def __new__(
        cls,
        *,
        auto_now: bool | None = False,
        auto_now_add: bool | None = False,
        default_timezone: zoneinfo.ZoneInfo | None = None,
        force_timezone: zoneinfo.ZoneInfo | None = None,
        **kwargs: Any,
    ) -> BaseFieldType:
        """
        Initializes a new DateField instance.

        Configures auto-now and auto-now-add settings.
        Timezone information is inherently lost for `date` types.
        """
        # The datetimes lose the information anyway, so set remove_timezone to False.
        kwargs["remove_timezone"] = False

        kwargs = {
            **kwargs,
            **{k: v for k, v in locals().items() if k not in CLASS_DEFAULTS},
        }
        return super().__new__(cls, **kwargs)

    @classmethod
    def get_column_type(cls, kwargs: dict[str, Any]) -> Any:
        """
        Returns the SQLAlchemy column type for a DateField.
        """
        return sqlalchemy.Date()


class DurationField(FieldFactory, datetime.timedelta):
    """
    Represents a duration field, storing `datetime.timedelta` objects.
    """

    field_type = datetime.timedelta

    @classmethod
    def get_column_type(cls, kwargs: dict[str, Any]) -> Any:
        """
        Returns the SQLAlchemy column type for a DurationField.
        """
        return sqlalchemy.Interval()

    @classmethod
    def operator_to_clause(
        cls,
        field_obj: BaseFieldType,
        field_name: str,
        operator: str,
        table: sqlalchemy.Table,
        value: Any,
        original_fn: Any,
    ) -> Any:
        """
        Overwrite for isempty.

        Args:
            field_name: The name of the column to apply the operator to.
            operator: The operation code (e.g., 'iexact', 'contains', 'isnull').
            table: The SQLAlchemy Table object the column belongs to.
            value: The value to compare against.
            original_fn: The field object original function.

        Returns:
            A SQLAlchemy clause suitable for use in a query's WHERE statement.

        Raises:
            KeyError: If 'field_name' does not correspond to an existing column in the table.
            AttributeError: If the mapped operator does not exist as a method on the column.
        """
        mapped_operator = field_obj.operator_mapping.get(operator, operator)
        if mapped_operator == "isempty":
            column = table.columns[field_name]
            is_empty = sqlalchemy.or_(column.is_(None), column == datetime.timedelta())
            return is_empty if value else sqlalchemy.not_(is_empty)
        else:
            return original_fn(field_name, operator, table, value)


class TimeField(FieldFactory, datetime.time):
    """
    Represents a time field.
    """

    field_type = datetime.time

    def __new__(cls, with_timezone: bool = False, **kwargs: Any) -> BaseFieldType:
        """
        Initializes a new TimeField instance.

        Allows specifying whether the time field should include timezone information.
        """
        kwargs = {
            **kwargs,
            **{k: v for k, v in locals().items() if k not in CLASS_DEFAULTS},
        }
        return super().__new__(cls, **kwargs)

    @classmethod
    def get_column_type(cls, kwargs: dict[str, Any]) -> Any:
        """
        Returns the SQLAlchemy column type for a TimeField.

        The column type is `sqlalchemy.Time`, with optional timezone support.
        """
        return sqlalchemy.Time(kwargs.get("with_timezone") or False)


class JSONField(FieldFactory, pydantic.Json):
    """
    Represents a JSON field.

    This field stores arbitrary JSON data.
    """

    field_type = Any

    @classmethod
    def get_column_type(cls, kwargs: dict[str, Any]) -> Any:
        """
        Returns the SQLAlchemy column type for a JSONField.
        """
        none_as_null = kwargs.get("none_as_null")
        if none_as_null is None:
            none_as_null = bool(kwargs.get("null"))
        sqltype = sqlalchemy.JSON(none_as_null=none_as_null)
        if kwargs.get("no_jsonb"):
            return sqltype
        return sqltype.with_variant(
            postgresql.JSONB(none_as_null=none_as_null),
            "postgres",
            "postgresql",
        )

    @classmethod
    def get_default_value(cls, field_obj: BaseFieldType, original_fn: Any = None) -> Any:
        """
        Retrieves the default value for the JSONField.

        Ensures that mutable default structures (lists, dictionaries) are
        deep-copied to prevent unintended shared references.
        """
        default = original_fn()
        # Copy mutable structures to prevent shared references.
        if isinstance(default, list | dict):
            default = copy.deepcopy(default)
        return default

    @classmethod
    def customize_default_for_server_default(
        cls, field_obj: BaseFieldType, default: Any, original_fn: Any = None
    ) -> Any:
        """
        Customizes the default value for server-side defaults in a JSONField.

        If the default is callable, it's invoked. The value is then
        serialized to JSON using `orjson` and wrapped in `sqlalchemy.text`
        for database compatibility.
        """
        if callable(default):
            default = default()
        if not isinstance(default, str):
            default = orjson.dumps(default)
        return sqlalchemy.text(":value").bindparams(value=default)

    @classmethod
    def operator_to_clause(
        cls,
        field_obj: BaseFieldType,
        field_name: str,
        operator: str,
        table: sqlalchemy.Table,
        value: Any,
        original_fn: Any,
    ) -> Any:
        """
        Overwrite for isempty. Change logic for isnull to select also json "null".

        Args:
            field_name: The name of the column to apply the operator to.
            operator: The operation code (e.g., 'iexact', 'contains', 'isnull').
            table: The SQLAlchemy Table object the column belongs to.
            value: The value to compare against.
            original_fn: The field object original function.

        Returns:
            A SQLAlchemy clause suitable for use in a query's WHERE statement.

        Raises:
            KeyError: If 'field_name' does not correspond to an existing column in the table.
            AttributeError: If the mapped operator does not exist as a method on the column.
        """
        mapped_operator = field_obj.operator_mapping.get(operator, operator)
        if mapped_operator == "isempty":
            column = table.columns[field_name]
            casted = sqlalchemy.cast(column, sqlalchemy.Text())
            is_empty = sqlalchemy.or_(
                column.is_(sqlalchemy.null()),
                casted.in_(["null", "[]", "{}", "0", "0.0", '""']),
            )
            return is_empty if value else sqlalchemy.not_(is_empty)
        elif mapped_operator == "isnull":
            column = table.columns[field_name]
            casted = sqlalchemy.cast(column, sqlalchemy.Text())
            # we cannot check against sqlalchemy.JSON.NULL
            isnull = sqlalchemy.or_(column.is_(sqlalchemy.null()), casted == "null")
            return isnull if value else sqlalchemy.not_(isnull)
        else:
            return original_fn(field_name, operator, table, value)


class BinaryField(FieldFactory, bytes):
    """
    Represents a binary field, storing bytes.
    """

    field_type = bytes

    def __new__(cls, *, max_length: int | None = None, **kwargs: Any) -> BaseFieldType:
        """
        Initializes a new BinaryField instance.

        Allows specifying a maximum length for the binary data.
        """
        kwargs = {
            **kwargs,
            **{k: v for k, v in locals().items() if k not in CLASS_DEFAULTS},
        }
        return super().__new__(cls, **kwargs)

    @classmethod
    def get_column_type(cls, kwargs: dict[str, Any]) -> Any:
        """
        Returns the SQLAlchemy column type for a BinaryField.

        Uses `sqlalchemy.LargeBinary` with the specified maximum length.
        """
        return sqlalchemy.LargeBinary(length=kwargs.get("max_length"))

    @classmethod
    def operator_to_clause(
        cls,
        field_obj: BaseFieldType,
        field_name: str,
        operator: str,
        table: sqlalchemy.Table,
        value: Any,
        original_fn: Any,
    ) -> Any:
        """
        Overwrite for isempty.

        Args:
            field_name: The name of the column to apply the operator to.
            operator: The operation code (e.g., 'iexact', 'contains', 'isnull').
            table: The SQLAlchemy Table object the column belongs to.
            value: The value to compare against.
            original_fn: The field object original function.

        Returns:
            A SQLAlchemy clause suitable for use in a query's WHERE statement.

        Raises:
            KeyError: If 'field_name' does not correspond to an existing column in the table.
            AttributeError: If the mapped operator does not exist as a method on the column.
        """
        mapped_operator = field_obj.operator_mapping.get(operator, operator)
        if mapped_operator == "isempty":
            column = table.columns[field_name]
            is_empty = sqlalchemy.or_(column.is_(None), column == b"")
            return is_empty if value else sqlalchemy.not_(is_empty)
        else:
            return original_fn(field_name, operator, table, value)


class UUIDField(FieldFactory, uuid.UUID):
    """
    Represents a UUID field.
    """

    field_type = uuid.UUID

    def __new__(cls, **kwargs: Any) -> BaseFieldType:
        """
        Initializes a new UUIDField instance.
        """
        kwargs = {
            **kwargs,
            **{k: v for k, v in locals().items() if k not in CLASS_DEFAULTS},
        }

        return super().__new__(cls, **kwargs)

    @classmethod
    def get_column_type(cls, kwargs: dict[str, Any]) -> Any:
        """
        Returns the SQLAlchemy column type for a UUIDField.

        Uses `sqlalchemy.Uuid` with native UUID support.
        """
        return sqlalchemy.Uuid(as_uuid=True, native_uuid=True)


class ChoiceField(FieldFactory):
    """
    Represents a choice field based on a Python Enum.

    This field enforces that values must be members of a specified Enum class.
    """

    def __new__(
        cls,
        choices: type[enum.Enum],
        **kwargs: Any,
    ) -> BaseFieldType:
        """
        Initializes a new ChoiceField instance.

        Requires a `choices` argument, which must be an Enum class.
        """
        return super().__new__(cls, choices=choices, **kwargs)

    @classmethod
    def get_pydantic_type(cls, kwargs: dict[str, Any]) -> Any:
        """
        Returns the Pydantic type for the ChoiceField, which is the Enum class itself.
        """
        return kwargs["choices"]

    @classmethod
    def validate(cls, kwargs: dict[str, Any]) -> None:
        """
        Validates the keyword arguments for a ChoiceField.

        Ensures that `choices` is provided and is an instance of `EnumMeta` (an Enum class).
        """
        choice_class = kwargs.get("choices")
        if choice_class is None or not isinstance(choice_class, EnumMeta):
            raise FieldDefinitionError("ChoiceField choices must be an Enum")

    @classmethod
    def get_column_type(cls, kwargs: dict[str, Any]) -> sqlalchemy.Enum:
        """
        Returns the SQLAlchemy column type for a ChoiceField.

        Uses `sqlalchemy.Enum` with the provided Enum class.
        """
        choice_class = kwargs.get("choices")
        return sqlalchemy.Enum(choice_class)

    @classmethod
    def customize_default_for_server_default(
        cls, field_obj: BaseFieldType, default: Any, original_fn: Any = None
    ) -> Any:
        """
        Customizes the default value for server-side defaults in a ChoiceField.

        If the default is callable, it's invoked. The enum member's name
        is then used as the value for the server default.
        """
        if callable(default):
            default = default()
        return sqlalchemy.text(":value").bindparams(value=default.name)


class CharChoiceField(ChoiceField):
    """
    Represents a choice field where the choices are backed by character strings.

    This field extends `ChoiceField` by allowing a `max_length` for the string
    representation of the enum member names.
    """

    @classmethod
    def validate(cls, kwargs: dict[str, Any]) -> None:
        """
        Validates the keyword arguments for a CharChoiceField.

        Sets a default `max_length` and renames it to `key_max_length`
        to avoid Pydantic conflicts. It also verifies that no enum member name
        exceeds the specified `max_length`.
        """
        super().validate(kwargs)
        kwargs.setdefault("max_length", 30)
        # We need to rename max_length. Pydantic will otherwise raise a TypeError.
        max_length = kwargs["key_max_length"] = kwargs.pop("max_length")
        choice_class = kwargs.get("choices")
        if max_length is not None:
            for k in choice_class.__members__:
                if len(k) > max_length:
                    raise FieldDefinitionError(
                        f"ChoiceField choice name {k} is longer than {max_length} characters. "
                        "Alternatively raise the max_length via explicitly passing a max_length "
                        "argument or set it to None (less performant)."
                    )

    @classmethod
    def get_column_type(cls, kwargs: dict[str, Any]) -> Any:
        """
        Returns the SQLAlchemy column type for a CharChoiceField.

        Uses `sqlalchemy.Text` if no `key_max_length` is specified,
        otherwise `sqlalchemy.String` with the provided length.
        """
        max_length: int | None = kwargs.get("key_max_length")
        return (
            sqlalchemy.Text(collation=kwargs.get("collation"))
            if max_length is None
            else sqlalchemy.String(length=max_length, collation=kwargs.get("collation"))
        )

    @classmethod
    def to_model(
        cls, field_obj: BaseFieldType, field_name: str, value: Any, original_fn: Any = None
    ) -> dict[str, Any]:
        """
        Converts the field value to the model representation.

        Checks the value against the enum choices.
        """
        return {field_name: cls.check(field_obj, value=value)}

    @classmethod
    def clean(
        cls,
        field_obj: BaseFieldType,
        field_name: str,
        value: Any,
        for_query: bool = False,
        original_fn: Any = None,
    ) -> dict[str, Any]:
        """
        Cleans the field value before use, typically for queries or storage.

        Converts the value to its enum member name.
        """
        return {field_name: cls.check(field_obj, value=value).name}

    @classmethod
    def check(cls, field_obj: BaseFieldType, value: Any, original_fn: Any = None) -> Any:
        """
        Checks and converts the input value to the corresponding enum member.

        Handles both string and Enum input values, raising `ValueError` for invalid keys.
        """
        if isinstance(value, Enum):
            value = value.name
        if not isinstance(value, str):
            raise ValueError("Value must be a string or enum member.")
        try:
            return field_obj.choices.__members__[value]
        except KeyError:
            raise ValueError(f"Invalid enum key {value}.") from None

    @classmethod
    def get_default_value(cls, field_obj: BaseFieldType, original_fn: Any = None) -> Any:
        """
        Retrieves the default value for the CharChoiceField.

        Returns the name of the default enum member.
        """
        default = original_fn()
        return default.name


class PasswordField(CharField):
    """
    Represents a password field.

    This field can derive a stored password from an input value (e.g., hashing)
    and optionally keeps the original password for comparison purposes.
    """

    def __new__(
        cls,
        derive_fn: Callable[[str], str] | None = None,
        **kwargs: Any,
    ) -> BaseFieldType:
        """
        Initializes a new PasswordField instance.

        Allows specifying a `derive_fn` for transforming the password,
        and sets `keep_original` based on its presence.
        """
        kwargs.setdefault("keep_original", derive_fn is not None)
        return super().__new__(cls, derive_fn=derive_fn, **kwargs)

    @classmethod
    def get_embedded_fields(
        cls,
        field_obj: BaseFieldType,
        name: str,
        fields: dict[str, BaseFieldType],
        original_fn: Any = None,
    ) -> dict[str, BaseFieldType]:
        """
        Retrieves any embedded fields associated with the PasswordField.

        If `keep_original` is True, it adds a placeholder field for the
        original password.
        """
        retdict: dict[str, BaseFieldType] = {}
        # TODO: check if it works in embedded settings or embed_field is required
        if field_obj.keep_original:
            original_pw_name = f"{name}_original"
            if original_pw_name not in fields:
                retdict[original_pw_name] = cast(
                    BaseFieldType,
                    _PlaceholderField(
                        pydantic_field_type=str,
                        null=True,
                        exclude=True,
                        read_only=True,
                        name=original_pw_name,
                        owner=field_obj.owner,
                    ),
                )

        return retdict

    @classmethod
    def to_model(
        cls, field_obj: BaseFieldType, field_name: str, value: Any, original_fn: Any = None
    ) -> dict[str, Any]:
        """
        Converts the password value to the model representation.

        Handles password confirmation if the value is a tuple/list.
        Applies `derive_fn` during 'set' or 'init' phases and
        clears the original password after saving/loading if `keep_original` is true.
        """
        if isinstance(value, tuple | list):
            # Despite an != should not be a problem here, make sure that strange logics
            # doesn't leak timings of the password.
            if not compare_digest(value[0], value[1]):
                raise ValueError("Password doesn't match.")
            else:
                value = value[0]
        retval: dict[str, Any] = {}
        phase = CURRENT_PHASE.get()
        derive_fn = cast(Callable[[str], str] | None, field_obj.derive_fn)
        if phase in {"set", "init"} and derive_fn is not None:
            retval[field_name] = derive_fn(value)
            if getattr(field_obj, "keep_original", False):
                retval[f"{field_name}_original"] = value
        else:
            retval[field_name] = value
            # Blank the original password after saving or loading for security.
            if phase in {"post_insert", "post_update", "load"} and getattr(
                field_obj, "keep_original", False
            ):
                retval[f"{field_name}_original"] = None

        return retval

    @classmethod
    def validate(cls, kwargs: dict[str, Any]) -> None:
        """
        Validates the keyword arguments for a PasswordField.

        Sets default `secret` to True and `max_length` to 255.
        """
        kwargs.setdefault("secret", True)
        kwargs.setdefault("max_length", 255)
        super().validate(kwargs)


class EmailField(CharField):
    """
    Represents an email address field.

    This field validates input as a valid email format.
    """

    field_type = EmailStr

    @classmethod
    def validate(cls, kwargs: dict[str, Any]) -> None:
        """
        Validates the keyword arguments for an EmailField.

        Sets a default `max_length` for email addresses.
        """
        kwargs.setdefault("max_length", 255)
        super().validate(kwargs)


UrlString = Annotated[AnyUrl, pydantic.AfterValidator(lambda v: v if v is None else str(v))]


class URLField(CharField):
    """
    Represents a URL field.

    This field validates input as a valid URL format.
    """

    field_type = UrlString  # type: ignore

    @classmethod
    def validate(cls, kwargs: dict[str, Any]) -> None:
        """
        Validates the keyword arguments for a URLField.

        Sets a default `max_length` for URLs.
        """
        kwargs.setdefault("max_length", 255)
        super().validate(kwargs)


class IPAddressField(FieldFactory, str):
    """
    Represents an IP address field (IPv4 or IPv6).

    This field validates and stores IP addresses.
    """

    field_type = IPvAnyAddress

    def __new__(
        cls,
        **kwargs: Any,
    ) -> BaseFieldType:
        """
        Initializes a new IPAddressField instance.
        """
        kwargs = {
            **kwargs,
            **{key: value for key, value in locals().items() if key not in CLASS_DEFAULTS},
        }

        return super().__new__(cls, **kwargs)

    @classmethod
    def get_column_type(cls, kwargs: dict[str, Any]) -> IPAddress:
        """
        Returns the SQLAlchemy column type for an IPAddressField.
        """
        return IPAddress()

    @staticmethod
    def is_native_type(value: str) -> bool:
        """
        Checks if the given value is already a native IP address type.
        """
        return isinstance(value, ipaddress.IPv4Address | ipaddress.IPv6Address)

    @classmethod
    def check(cls, field_obj: BaseFieldType, value: Any, original_fn: Any = None) -> Any:
        """
        Checks and converts the input value to a native IP address object.

        Raises `ValueError` if the input is not a valid IP address string.
        """
        if value is None:
            return None
        if cls.is_native_type(value):
            return value

        try:
            return ipaddress.ip_address(value)
        except ValueError as exc:
            # Re-raise with a more specific message.
            raise ValueError("Must be a real IP.") from exc


Monkay(
    globals(),
    deprecated_lazy_imports={
        "ComputedField": {
            "path": ".computed_field.ComputedField",
            "reason": "The import path changed.",
            "new_attribute": "edgy.core.db.fields.ComputedField",
        },
        "PlaceholderField": {
            "path": lambda: _PlaceholderField,
            "reason": "The import path changed.",
            "new_attribute": "edgy.core.db.fields.PlaceholderField",
        },
        "AutoNowMixin": {
            "path": lambda: _AutoNowMixin,
            "reason": "We export mixins now from edgy.core.db.fields.mixins.",
            "new_attribute": "edgy.core.db.fields.mixins.AutoNowMixin",
        },
    },
)
