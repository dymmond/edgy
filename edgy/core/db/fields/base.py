import decimal
from functools import cached_property
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    ClassVar,
    Dict,
    Optional,
    Pattern,
    Sequence,
    Union,
)

from pydantic._internal import _repr
from pydantic.fields import FieldInfo

from edgy.core.connection.registry import Registry
from edgy.exceptions import FieldDefinitionError
from edgy.types import Undefined

if TYPE_CHECKING:
    from sqlalchemy import Column, Constraint

edgy_setattr = object.__setattr__


class BaseField(FieldInfo, _repr.Representation):
    """
    The base field for all Edgy data model fields.
    """

    __namespace__: ClassVar[Union[Dict[str, Any], None]] = None

    def __init__(
        self,
        *,
        default: Any = Undefined,
        title: Optional[str] = None,
        description: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        self.max_digits: str = kwargs.pop("max_digits", None)
        self.decimal_places: str = kwargs.pop("decimal_places", None)
        self.server_default: Any = kwargs.pop("server_default", None)

        super().__init__(**kwargs)

        self.null: bool = kwargs.pop("null", False)
        if self.null and default is Undefined:
            default = None
        if default is not Undefined:
            self.default = default
        if (
            (default is not None)
            and default != Undefined
            or (self.server_default is not None and self.server_default != Undefined)
        ):
            self.null = True

        self.defaulf_factory: Optional[Callable[..., Any]] = kwargs.pop(
            "defaulf_factory", Undefined
        )
        self.field_type: Any = kwargs.pop("__type__", None)
        self.__original_type__: type = kwargs.pop("__original_type__", None)
        self.primary_key: bool = kwargs.pop("primary_key", False)
        self.column_type: Optional[Any] = kwargs.pop("column_type", None)
        self.constraints: Sequence["Constraint"] = kwargs.pop("constraints", None)
        self.title = title
        self.description = description
        self.skip_absorption_check: bool = kwargs.pop("skip_absorption_check", False)
        self.read_only: bool = kwargs.pop("read_only", False)
        self.help_text: str = kwargs.pop("help_text", None)
        self.pattern: Pattern = kwargs.pop("pattern", None)
        self.autoincrement: bool = kwargs.pop("autoincrement", False)
        self.related_name: str = kwargs.pop("related_name", None)
        self.unique: bool = kwargs.pop("unique", False)
        self.index: bool = kwargs.pop("index", False)
        self.choices: Sequence = kwargs.pop("choices", None)
        self.owner: Any = kwargs.pop("owner", None)
        self.name: str = kwargs.pop("name", None)
        self.alias: str = kwargs.pop("name", None)
        self.regex: str = kwargs.pop("regex", None)
        self.format: str = kwargs.pop("format", None)
        self.min_length: Optional[Union[int, float, decimal.Decimal]] = kwargs.pop(
            "min_length", None
        )
        self.max_length: Optional[Union[int, float, decimal.Decimal]] = kwargs.pop(
            "max_length", None
        )
        self.minimum: Optional[Union[int, float, decimal.Decimal]] = kwargs.pop(
            "minimum", None
        )
        self.maximum: Optional[Union[int, float, decimal.Decimal]] = kwargs.pop(
            "maximum", None
        )
        self.multiple_of: Optional[Union[int, float, decimal.Decimal]] = kwargs.pop(
            "multiple_of", None
        )
        self.through: Any = kwargs.pop("through", None)
        self.server_onupdate: Any = kwargs.pop("server_onupdate", None)
        self.registry: Registry = kwargs.pop("registry", None)
        self.comment: str = kwargs.pop("comment", None)
        self.secret: bool = kwargs.pop("secret", False)
        # hackaround to prevent multi call of get_embedded_fields
        # FIXME: should only call the metaclasses
        self.embedded_fields_initialized = False

        if self.primary_key:
            default_value = default
            self.raise_for_non_default(
                default=default_value, server_default=self.server_default
            )

        for name, value in kwargs.items():
            edgy_setattr(self, name, value)

        if self.primary_key:
            self.field_type = Any
            self.null = True

        if isinstance(self.default, bool):
            self.null = True
        self.__namespace__ = {
            k: v for k, v in self.__dict__.items() if k != "__namespace__"
        }

    @property
    def namespace(self) -> Any:
        """Returns the properties added to the fields in a dict format"""
        return self.__namespace__

    def is_required(self) -> bool:
        """Check if the argument is required.

        Returns:
            `True` if the argument is required, `False` otherwise.
        """
        required = False if self.null else True
        return bool(required and not self.primary_key)

    def raise_for_non_default(self, default: Any, server_default: Any) -> Any:
        has_default: bool = True
        has_server_default: bool = True

        if default is None or default is False:
            has_default = False
        if server_default is None or server_default is False:
            has_server_default = False

        if not self.field_type == int and not has_default and not has_server_default:
            raise FieldDefinitionError(
                "Primary keys other then IntegerField and BigIntegerField, must provide a default or a server_default."
            )

    def get_alias(self) -> str:
        """
        Used to translate the model column names into database column tables.
        """
        return self.name

    def is_primary_key(self) -> bool:
        """
        Sets the autoincrement to True if the field is primary key.
        """
        if self.primary_key:
            self.autoincrement = True
        return False

    def has_default(self) -> bool:
        """Checks if the field has a default value set"""
        return bool(self.default is not None and self.default is not Undefined)

    def get_columns(self, field_name: str) -> Sequence["Column"]:
        """
        Returns the columns of the field being declared.
        """
        raise NotImplementedError()

    def clean(self, field_name: str, value: Any) -> Dict[str, Any]:
        """
        Runs the checks for the fields being validated.
        """
        raise NotImplementedError()

    def get_embedded_fields(
        self, field_name: str, field_mapping: Dict[str, "BaseField"]
    ) -> Dict[str, "BaseField"]:
        """
        Define extra fields on the fly. Often no owner is available yet.

        Arguments are:
        name: the field name
        field_mapping: the existing fields
        """
        return {}

    def expand_relationship(self, value: Any) -> Any:
        """
        Used to be overwritten by any Link class.
        """
        return value

    def get_related_name(self) -> str:
        """Returns the related name used for reverse relations"""
        return self.related_name

    def get_constraints(self) -> Any:
        return self.constraints

    def get_default_value(self) -> Any:
        # single default
        default = getattr(self, "default", None)
        if callable(default):
            return default()
        return default

    def get_default_values(self, field_name: str, cleaned_data: Dict[str, Any]) -> Any:
        # for multidefaults overwrite in subclasses get_default_values to
        # parse default values differently
        # NOTE: multi value fields should always check here if defaults were already applied
        if field_name in cleaned_data:
            return {}
        return {field_name: self.get_default_value()}


class BaseCompositeField(BaseField):
    def translate_name(self, name: str) -> str:
        """translate name for inner objects and parsing values"""
        return name

    def get_composite_fields(self) -> Dict[str, BaseField]:
        """return dictionary of fields with untranslated names"""
        raise NotImplementedError()

    @cached_property
    def composite_fields(self) -> Dict[str, BaseField]:
        # return untranslated names
        return self.get_composite_fields()

    def clean(self, field_name: str, value: Any) -> Dict[str, Any]:
        """
        Runs the checks for the fields being validated.
        """
        result = {}
        if isinstance(value, dict):
            for sub_name, field in self.composite_fields.items():
                translated_name = self.translate_name(sub_name)
                if translated_name not in value:
                    raise ValueError(f"Missing key: {sub_name} for {field_name}")
                for k, v in field.clean(sub_name, value[translated_name]).items():
                    result[k] = v
        else:
            for sub_name, field in self.composite_fields.items():
                translated_name = self.translate_name(sub_name)
                if not hasattr(value, translated_name):
                    raise ValueError(
                        f"Missing attribute: {translated_name} for {field_name}"
                    )
                for k, v in field.clean(sub_name, getattr(value, translated_name)):
                    result[k] = v

        return result

    def get_default_values(self, field_name: str, cleaned_data: Dict[str, Any]) -> Any:
        cleaned_data_result = {}
        for sub_field_name, field in self.composite_fields.items():
            # here we don't need to translate, there is no inner object
            for sub_field_name_new, default_value in field.get_default_values(
                sub_field_name, cleaned_data
            ):
                if (
                    sub_field_name_new not in cleaned_data
                    and sub_field_name_new not in cleaned_data_result
                ):
                    cleaned_data_result[sub_field_name_new] = default_value
        return cleaned_data_result
