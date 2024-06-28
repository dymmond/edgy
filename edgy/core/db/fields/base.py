import copy
import decimal
from functools import cached_property
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Dict,
    FrozenSet,
    Literal,
    Optional,
    Pattern,
    Sequence,
    Tuple,
    Type,
    Union,
    cast,
)

import sqlalchemy
from pydantic import BaseModel
from pydantic.fields import FieldInfo

from edgy.core.connection.registry import Registry
from edgy.types import Undefined

if TYPE_CHECKING:
    from edgy import Model, ReflectModel

def _removesuffix(text: str, suffix: str) -> str:
    # TODO: replace with _removesuffix when python3.9 is minimum
    if text.endswith(suffix):
        return text[: -len(suffix)]
    else:
        return text


class BaseField(FieldInfo):
    """
    The base field for all Edgy data model fields.
    """

    __namespace__: ClassVar[Union[Dict[str, Any], None]] = None

    def __init__(
        self,
        *,
        default: Any = Undefined,
        server_default: Any = Undefined,
        inherit: bool = True,
        **kwargs: Any,
    ) -> None:
        self.max_digits: str = kwargs.pop("max_digits", None)
        self.decimal_places: str = kwargs.pop("decimal_places", None)
        self.server_default: Any = server_default
        self.read_only: bool = kwargs.pop("read_only", False)
        self.primary_key: bool = kwargs.pop("primary_key", False)
        self.autoincrement: bool = kwargs.pop("autoincrement", False)
        self.inherit = inherit

        super().__init__(**kwargs)

        self.null: bool = kwargs.pop("null", False)
        if self.null and default is Undefined:
            default = None
        if default is not Undefined:
            self.default = default
        if (default is not None and default is not Undefined) or (
            self.server_default is not None and self.server_default != Undefined
        ):
            self.null = True
        self.field_type: Any = kwargs.pop("__type__", None)
        self.__original_type__: type = kwargs.pop("__original_type__", None)
        self.column_type: Optional[Any] = kwargs.pop("column_type", None)
        self.constraints: Sequence[sqlalchemy.Constraint] = kwargs.pop("constraints", [])
        self.skip_absorption_check: bool = kwargs.pop("skip_absorption_check", False)
        self.help_text: Optional[str] = kwargs.pop("help_text", None)
        self.pattern: Pattern = kwargs.pop("pattern", None)
        self.unique: bool = kwargs.pop("unique", False)
        self.index: bool = kwargs.pop("index", False)
        self.choices: Sequence = kwargs.pop("choices", [])
        self.owner: Union[Type["Model"], Type["ReflectModel"]] = kwargs.pop("owner", None)
        # field name, set when retrieving
        self.name: str = kwargs.get("name", None)
        self.alias: str = kwargs.pop("name", None)
        self.regex: str = kwargs.pop("regex", None)
        self.format: str = kwargs.pop("format", None)
        self.min_length: Optional[int] = kwargs.pop("min_length", None)
        self.max_length: Optional[int] = kwargs.pop("max_length", None)
        self.minimum: Optional[Union[int, float, decimal.Decimal]] = kwargs.pop("minimum", None)
        self.maximum: Optional[Union[int, float, decimal.Decimal]] = kwargs.pop("maximum", None)
        self.multiple_of: Optional[Union[int, float, decimal.Decimal]] = kwargs.pop("multiple_of", None)
        self.server_onupdate: Any = kwargs.pop("server_onupdate", None)
        self.registry: Registry = kwargs.pop("registry", None)
        self.comment: str = kwargs.pop("comment", None)
        self.secret: bool = kwargs.pop("secret", False)


        # set remaining attributes
        for name, value in kwargs.items():
            setattr(self, name, value)

        if self.primary_key:
            self.field_type = Any
            self.null = True

        if isinstance(self.default, bool):
            self.null = True
        self.__namespace__ = {k: v for k, v in self.__dict__.items() if k != "__namespace__"}

    @property
    def namespace(self) -> Any:
        """Returns the properties added to the fields in a dict format"""
        return self.__namespace__

    def is_required(self) -> bool:
        """Check if the argument is required.

        Returns:
            `True` if the argument is required, `False` otherwise.
        """
        if self.primary_key:
            if self.autoincrement:
                return False
        return False if self.null or self.server_default else True

    def get_alias(self) -> str:
        """
        Used to translate the model column names into database column tables.
        """
        return self.name

    def has_default(self) -> bool:
        """Checks if the field has a default value set"""
        return bool(self.default is not None and self.default is not Undefined)

    def get_columns(self, name: str) -> Sequence[sqlalchemy.Column]:
        """
        Returns the columns of the field being declared.
        """
        return []

    def get_column_names(self, name: str="") -> FrozenSet[str]:
        if name:
            return self.owner.meta.field_to_column_names[name]
        return self.owner.meta.field_to_column_names[self.name]

    def clean(self, field_name: str, value: Any, for_query: bool=False) -> Dict[str, Any]:
        """
        Validates a value and transform it into columns which can be used for querying and saving.
        for_query: is used for querying. Should have all columns used for querying set.
        """
        return {}

    def to_model(self, field_name: str, value: Any, phase: str = "") -> Dict[str, Any]:
        """
        Inverse of clean. Transforms column(s) to a field for a pydantic model (EdgyBaseModel).
        Validation happens later.
        """
        return {field_name: value}

    def get_embedded_fields(self, field_name: str, fields_mapping: Dict[str, "BaseField"]) -> Dict[str, "BaseField"]:
        """
        Define extra fields on the fly. Often no owner is available yet.

        Arguments are:
        name: the field name
        fields_mapping: the existing fields

        Note: the returned fields are changed after return, so you should
              return new fields or copies. Also set the owner of the field to them before returning
        """
        return {}

    def embed_field(self, prefix: str, new_fieldname:str, owner: Optional[Union[Type["Model"], Type["ReflectModel"]]]=None, parent: Optional["BaseField"]=None) -> Optional["BaseField"]:
        """
        Embed this field or return None to prevent embedding.
        Must return a copy with name and owner set when not returning None.
        """
        field_copy = copy.copy(self)
        field_copy.name = new_fieldname
        field_copy.owner = owner  # type: ignore
        return field_copy

    def get_constraints(self) -> Any:
        return self.constraints

    def get_global_constraints(self, name: str, columns: Sequence[sqlalchemy.Column]) -> Sequence[sqlalchemy.Constraint]:
        """Return global constraints and indexes.
        Useful for multicolumn fields
        """
        return []

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
        # NOTE: when build meta fields without columns this should be empty
        if field_name in cleaned_data:
            return {}
        return {field_name: self.get_default_value()}


class Field(BaseField):
    # defines compatibility fallbacks check and get_column

    def check(self, value: Any) -> Any:
        """
        Runs the checks for the fields being validated. Single Column.
        """
        return value

    def clean(self, name: str, value: Any, for_query: bool=False) -> Dict[str, Any]:
        """
        Runs the checks for the fields being validated. Multiple columns possible
        """
        return {name: self.check(value)}

    def get_column(self, name: str) -> Optional[sqlalchemy.Column]:
        """
        Return a single column for the field declared. Return None for meta fields.
        """
        constraints = self.get_constraints()
        return sqlalchemy.Column(
            name,
            self.column_type,
            *constraints,
            primary_key=self.primary_key,
            autoincrement=self.autoincrement,
            nullable=self.null,
            index=self.index,
            unique=self.unique,
            default=self.default,
            comment=self.comment,
            server_default=self.server_default,
            server_onupdate=self.server_onupdate,
        )

    def get_columns(self, name: str) -> Sequence[sqlalchemy.Column]:
        column = self.get_column(name)
        if column is None:
            return []
        return [column]


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

    def clean(self, field_name: str, value: Any, for_query: bool=False) -> Dict[str, Any]:
        """
        Runs the checks for the fields being validated.
        """
        prefix = _removesuffix(field_name, self.name)
        result = {}
        if isinstance(value, dict):
            for sub_name, field in self.composite_fields.items():
                translated_name = self.translate_name(sub_name)
                if translated_name not in value:
                    if field.has_default() or not field.is_required():
                        continue
                    raise ValueError(f"Missing key: {sub_name} for {field_name}")
                result.update(field.clean(f"{prefix}{sub_name}", value[translated_name], for_query=for_query))
        else:
            for sub_name, field in self.composite_fields.items():
                translated_name = self.translate_name(sub_name)
                if not hasattr(value, translated_name):
                    if not for_query:
                        if field.has_default() or not field.is_required():
                            continue
                    raise ValueError(f"Missing attribute: {translated_name} for {field_name}")
                result.update(field.clean(f"{prefix}{sub_name}", getattr(value, translated_name), for_query=for_query))
        return result

    def to_model(self, field_name: str, value: Any, phase: str = "") -> Dict[str, Any]:
        """
        Runs the checks for the fields being validated.
        """
        result = {}
        if isinstance(value, dict):
            for sub_name, field in self.composite_fields.items():
                translated_name = self.translate_name(sub_name)
                if translated_name not in value:
                    continue
                result.update(field.to_model(sub_name, value.get(translated_name, None), phase=phase))
        else:
            for sub_name, field in self.composite_fields.items():
                translated_name = self.translate_name(sub_name)
                if not hasattr(value, translated_name):
                    continue
                result.update(field.to_model(sub_name, getattr(value, translated_name, None), phase=phase))

        return result

    def get_default_values(self, field_name: str, cleaned_data: Dict[str, Any]) -> Any:
        # fields should provide their own default which is used as long as they are in the fields_mapping
        return {}


class RelationshipField(BaseField):
    def traverse_field(self, path: str) -> Tuple[Any, str, str]:
        raise NotImplementedError()

    def is_cross_db(self) -> bool:
        raise NotImplementedError()


class PKField(BaseCompositeField):
    """
    Field for pk
    """

    def __init__(self, **kwargs: Any):
        kwargs["default"] = kwargs["server_default"] = None
        kwargs["__type__"] = kwargs["annotation"] = Any
        return super().__init__(
            **kwargs,
        )

    def __get__(self, instance: "Model", owner: Any = None) -> Union[Dict[str, Any], Any]:
        pkcolumns = cast(Sequence[str], self.owner.pkcolumns)
        pknames = cast(Sequence[str], self.owner.pknames)
        assert len(pkcolumns) >= 1
        if len(pknames) == 1:
            return getattr(instance, pknames[0], None)
        d = {}
        for key in pknames:
            translated_name = self.translate_name(key)
            field = instance.meta.fields_mapping.get(key)
            if field and hasattr(field, "__get__"):
                d[translated_name] = field.__get__(instance, owner)
            else:
                d[translated_name] = getattr(instance, key, None)
        for key in self.fieldless_pkcolumns:
            translated_name = self.translate_name(key)
            d[translated_name] = getattr(instance, key, None)
        return d

    def modify_input(self, name: str, kwargs: Dict[str, Any]) -> None:
        if name not in kwargs:
            return
        # check for collisions
        for pkname in self.owner.pknames:
            if pkname in kwargs:
                raise ValueError("Cannot specify a primary key field and the primary key itself")

    def embed_field(self, prefix: str, new_fieldname:str, owner: Optional[Union[Type["Model"], Type["ReflectModel"]]]=None, parent: Optional["BaseField"]=None) -> Optional[BaseField]:
        return None

    def clean(self, field_name: str, value: Any, for_query: bool = False) -> Dict[str, Any]:
        pknames = cast(Sequence[str], self.owner.pknames)
        pkcolumns = cast(Sequence[str], self.owner.pkcolumns)
        prefix = _removesuffix(field_name, self.name)
        assert len(pkcolumns) >= 1
        if (
            len(pknames) == 1
            and not self.is_incomplete
            and not isinstance(value, (dict, BaseModel))
        ):
            pkname = pknames[0]
            field = self.owner.meta.fields_mapping[pkname]
            return field.clean(f"{prefix}{pkname}", value, for_query=for_query)
        retdict =  super().clean(field_name, value, for_query=for_query)
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

    def to_model(self, field_name: str, value: Any, phase: str = "") -> Dict[str, Any]:
        pknames = cast(Sequence[str], self.owner.pknames)
        assert len(cast(Sequence[str], self.owner.pkcolumns)) >= 1
        if self.is_incomplete:
            raise ValueError("Cannot set an incomplete defined pk!")
        if (len(pknames) == 1
            # we first only redirect both
            and not isinstance(value, (dict, BaseModel))
        ):
            field = self.owner.meta.fields_mapping[pknames[0]]
            return field.to_model(pknames[0], value, phase=phase)
        return super().to_model(field_name, value, phase=phase)

    def get_composite_fields(self) -> Dict[str, BaseField]:
        return {field: self.owner.meta.fields_mapping[field] for field in cast(Sequence[str], self.owner.pknames)}

    @cached_property
    def fieldless_pkcolumns(self) -> FrozenSet[str]:
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

    def __init__(
        self,
        *,
        related_name: Union[str, Literal[False]] = "",
        reverse_name: str = "",
        **kwargs: Any,
    ) -> None:
        self.related_name = related_name
        # name used for backward relations
        # only useful if related_name = False because otherwise it gets overwritten
        self.reverse_name = reverse_name
        super().__init__(**kwargs)

    @property
    def target(self) -> Any:
        """
        The target of the ForeignKey model.
        """
        if not hasattr(self, "_target"):
            if isinstance(self.to, str):
                self._target = self.registry.models[self.to]  # type: ignore
            else:
                self._target = self.to
        return self._target

    @target.setter
    def target(self, value: Any) -> None:
        self._target = value

    @target.deleter
    def target(self, value: Any) -> None:
        try:
            delattr(self, "_target")
        except AttributeError:
            pass

    def is_cross_db(self) -> bool:
        return self.owner.meta.registry is not self.target.meta.registry

    def expand_relationship(self, value: Any) -> Any:
        """
        Returns the related object or the relationship object
        """
        return value

    def to_model(self, field_name: str, value: Any, phase: str = "") -> Dict[str, Any]:
        return {field_name: self.expand_relationship(value)}
