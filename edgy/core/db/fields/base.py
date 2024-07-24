import contextlib
import copy
from functools import cached_property
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    FrozenSet,
    Literal,
    Optional,
    Sequence,
    Tuple,
    Type,
    Union,
    cast,
)

import sqlalchemy
from pydantic import BaseModel
from pydantic.fields import FieldInfo

from edgy.types import Undefined

from .types import BaseFieldType, ColumnDefinitionModel

if TYPE_CHECKING:
    from edgy import Model, ReflectModel, Registry


def _removesuffix(text: str, suffix: str) -> str:
    # TODO: replace with _removesuffix when python3.9 is minimum
    if text.endswith(suffix):
        return text[: -len(suffix)]
    else:
        return text


class BaseField(BaseFieldType, FieldInfo):
    """
    The base field for Edgy data model fields. It provides some helpers additional to
    BaseFieldType and inherits from FieldInfo for pydantic integration.

    Allows factories to overwrite methods.
    """

    # defs to simplify the life (can be None actually)
    owner: Type["Model"]
    registry: "Registry"

    def __init__(
        self,
        *,
        default: Any = Undefined,
        server_default: Any = Undefined,
        **kwargs: Any,
    ) -> None:
        self.server_default = server_default
        if "__type__" in kwargs:
            kwargs["field_type"] = kwargs.pop("__type__")

        super().__init__(**kwargs)

        # set remaining attributes
        for name, value in kwargs.items():
            setattr(self, name, value)

        if self.null and default is Undefined:
            default = None
        if default is not Undefined:
            self.default = default
        if (default is not None and default is not Undefined) or (
            self.server_default is not None and self.server_default != Undefined
        ):
            self.null = True

        if self.primary_key:
            self.field_type = Any
            self.null = True

        if isinstance(self.default, bool):
            self.null = True

    def is_required(self) -> bool:
        """Check if the argument is required.

        Returns:
            `True` if the argument is required, `False` otherwise.
        """
        if self.primary_key and self.autoincrement:
            return False
        return not (self.null or self.server_default)

    def has_default(self) -> bool:
        """Checks if the field has a default value set"""
        return bool(self.default is not None and self.default is not Undefined)

    def get_columns(self, name: str) -> Sequence[sqlalchemy.Column]:
        """
        Returns the columns of the field being declared.
        """
        return []

    def embed_field(
        self,
        prefix: str,
        new_fieldname: str,
        owner: Optional[Union[Type["Model"], Type["ReflectModel"]]] = None,
        parent: Optional["BaseField"] = None,
    ) -> Optional["BaseField"]:
        """
        Embed this field or return None to prevent embedding.
        Must return a copy with name and owner set when not returning None.
        """
        field_copy = copy.copy(self)
        field_copy.name = new_fieldname
        field_copy.owner = owner  # type: ignore
        return field_copy

    def get_default_value(self) -> Any:
        # single default
        default = getattr(self, "default", None)
        if callable(default):
            return default()
        return default

    def get_default_values(
        self, field_name: str, cleaned_data: Dict[str, Any], is_update: bool = False
    ) -> Any:
        # for multidefaults overwrite in subclasses get_default_values to
        # parse default values differently
        # NOTE: multi value fields should always check here if defaults were already applied
        # NOTE: when build meta fields without columns this should be empty
        if field_name in cleaned_data:
            return {}
        return {field_name: self.get_default_value()}


class Field(BaseField):
    """
    Field with fallbacks and used for factories.
    """

    def check(self, value: Any) -> Any:
        """
        Runs the checks for the fields being validated. Single Column.
        """
        return value

    def clean(self, name: str, value: Any, for_query: bool = False) -> Dict[str, Any]:
        """
        Runs the checks for the fields being validated. Multiple columns possible
        """
        return {name: self.check(value)}

    def get_column(self, name: str) -> Optional[sqlalchemy.Column]:
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
            **column_model.model_dump(by_alias=True, exclude_none=True),
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

    def get_composite_fields(self) -> Dict[str, BaseFieldType]:
        """return dictionary of fields with untranslated names"""
        raise NotImplementedError()

    @cached_property
    def composite_fields(self) -> Dict[str, BaseFieldType]:
        # return untranslated names
        return self.get_composite_fields()

    def clean(self, field_name: str, value: Any, for_query: bool = False) -> Dict[str, Any]:
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
                result.update(
                    field.clean(f"{prefix}{sub_name}", value[translated_name], for_query=for_query)
                )
        else:
            for sub_name, field in self.composite_fields.items():
                translated_name = self.translate_name(sub_name)
                if not hasattr(value, translated_name):
                    if not for_query and (field.has_default() or not field.is_required()):
                        continue
                    raise ValueError(f"Missing attribute: {translated_name} for {field_name}")
                result.update(
                    field.clean(
                        f"{prefix}{sub_name}", getattr(value, translated_name), for_query=for_query
                    )
                )
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
                result.update(
                    field.to_model(sub_name, value.get(translated_name, None), phase=phase)
                )
        else:
            for sub_name, field in self.composite_fields.items():
                translated_name = self.translate_name(sub_name)
                if not hasattr(value, translated_name):
                    continue
                result.update(
                    field.to_model(sub_name, getattr(value, translated_name, None), phase=phase)
                )

        return result

    def get_default_values(
        self, field_name: str, cleaned_data: Dict[str, Any], is_update: bool = False
    ) -> Any:
        # fields should provide their own default which is used as long as they are in the fields mapping
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
        kwargs["field_type"] = kwargs["annotation"] = Any
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
            field = instance.meta.fields.get(key)
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

    def embed_field(
        self,
        prefix: str,
        new_fieldname: str,
        owner: Optional[Union[Type["Model"], Type["ReflectModel"]]] = None,
        parent: Optional[BaseFieldType] = None,
    ) -> Optional[BaseFieldType]:
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

    def to_model(self, field_name: str, value: Any, phase: str = "") -> Dict[str, Any]:
        pknames = cast(Sequence[str], self.owner.pknames)
        assert len(cast(Sequence[str], self.owner.pkcolumns)) >= 1
        if self.is_incomplete:
            raise ValueError("Cannot set an incomplete defined pk!")
        if (
            len(pknames) == 1
            # we first only redirect both
            and not isinstance(value, (dict, BaseModel))
        ):
            field = self.owner.meta.fields[pknames[0]]
            return field.to_model(pknames[0], value, phase=phase)
        return super().to_model(field_name, value, phase=phase)

    def get_composite_fields(self) -> Dict[str, BaseFieldType]:
        return {
            field: self.owner.meta.fields[field]
            for field in cast(Sequence[str], self.owner.pknames)
        }

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
                self._target = self.registry.models[self.to]
            else:
                self._target = self.to
        return self._target

    @target.setter
    def target(self, value: Any) -> None:
        self._target = value

    @target.deleter
    def target(self, value: Any) -> None:
        with contextlib.suppress(AttributeError):
            delattr(self, "_target")

    def is_cross_db(self) -> bool:
        return self.owner.meta.registry is not self.target.meta.registry

    def expand_relationship(self, value: Any) -> Any:
        """
        Returns the related object or the relationship object
        """
        return value

    def to_model(self, field_name: str, value: Any, phase: str = "") -> Dict[str, Any]:
        return {field_name: self.expand_relationship(value)}
