import decimal
from functools import cached_property
from typing import TYPE_CHECKING, Any, ClassVar, Dict, FrozenSet, Optional, Pattern, Sequence, Type, Union

from pydantic import BaseModel
from pydantic.fields import FieldInfo
from sqlalchemy import Column, Constraint, ForeignKeyConstraint

from edgy.core.connection.registry import Registry
from edgy.exceptions import FieldDefinitionError
from edgy.types import Undefined

if TYPE_CHECKING:
    from edgy import Model, ReflectModel

edgy_setattr = object.__setattr__

FK_CHAR_LIMIT = 63


def _removeprefix(text: str, prefix: str) -> str:
    # TODO: replace with removeprefix when python3.9 is minimum
    if text.startswith(prefix):
        return text[len(prefix) :]
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
        **kwargs: Any,
    ) -> None:
        self.max_digits: str = kwargs.pop("max_digits", None)
        self.decimal_places: str = kwargs.pop("decimal_places", None)
        self.server_default: Any = server_default
        self.read_only: bool = kwargs.pop("read_only", False)
        self.primary_key: bool = kwargs.pop("primary_key", False)
        if self.primary_key:
            self.read_only = True
            kwargs["frozen"] = True

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
        self.autoincrement: bool = kwargs.pop("autoincrement", False)
        self.column_type: Optional[Any] = kwargs.pop("column_type", None)
        self.constraints: Sequence["Constraint"] = kwargs.pop("constraints", [])
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
        # Prevent multiple initialization
        self.embedded_fields_initialized = False

        if self.primary_key:
            default_value = default
            self.raise_for_non_default(default=default_value, server_default=self.server_default)

        # set remaining attributes
        for name, value in kwargs.items():
            edgy_setattr(self, name, value)

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
        return False if self.null else True

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

    def has_default(self) -> bool:
        """Checks if the field has a default value set"""
        return bool(self.default is not None and self.default is not Undefined)

    def get_columns(self, name: str) -> Sequence["Column"]:
        """
        Returns the columns of the field being declared.
        """
        raise NotImplementedError()

    def clean(self, field_name: str, value: Any) -> Dict[str, Any]:
        """
        Validates a value and transform it into columns which can be used for querying and saving
        """
        raise NotImplementedError()

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

        Note: the returned fields are changed after return, so you should return new fields or copies. Also set the owner of the field to them before returning
        """
        return {}

    def get_constraints(self) -> Any:
        return self.constraints

    def get_global_constraints(self, name: str, columns: Sequence[Column]) -> Sequence[Constraint]:
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
        if field_name.endswith("pk"):
            prefix = field_name[:-2]
        else:
            prefix = ""
        result = {}
        if isinstance(value, dict):
            for sub_name, field in self.composite_fields.items():
                translated_name = self.translate_name(sub_name)
                if translated_name not in value:
                    raise ValueError(f"Missing key: {sub_name} for {field_name}")
                for k, v in field.clean(f"{prefix}{sub_name}", value[translated_name]).items():
                    result[k] = v
        else:
            for sub_name, field in self.composite_fields.items():
                translated_name = self.translate_name(sub_name)
                if not hasattr(value, translated_name):
                    raise ValueError(f"Missing attribute: {translated_name} for {field_name}")
                for k, v in field.clean(f"{prefix}{sub_name}", getattr(value, translated_name)).items():
                    result[k] = v
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
                for k, v in field.to_model(sub_name, value.get(translated_name, None), phase=phase).items():
                    result[k] = v
        else:
            for sub_name, field in self.composite_fields.items():
                translated_name = self.translate_name(sub_name)
                if not hasattr(value, translated_name):
                    continue
                for k, v in field.to_model(sub_name, getattr(value, translated_name, None), phase=phase).items():
                    result[k] = v

        return result

    def get_default_values(self, field_name: str, cleaned_data: Dict[str, Any]) -> Any:
        cleaned_data_result = {}
        for sub_field_name, field in self.composite_fields.items():
            # here we don't need to translate, there is no inner object
            for sub_field_name_new, default_value in field.get_default_values(sub_field_name, cleaned_data):
                if sub_field_name_new not in cleaned_data and sub_field_name_new not in cleaned_data_result:
                    cleaned_data_result[sub_field_name_new] = default_value
        return cleaned_data_result

    def get_columns(self, name: str) -> Sequence["Column"]:
        return []

    def is_required(self) -> bool:
        return False


class BaseForeignKey(BaseField):
    def __init__(
        self,
        *,
        on_update: str,
        on_delete: str,
        related_name: str = "",
        through: Any = None,
        **kwargs: Any,
    ) -> None:
        self.related_name = related_name
        self.through = through
        self.on_update = on_update
        self.on_delete = on_delete
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

    def expand_relationship(self, value: Any) -> Any:
        target = self.target

        if isinstance(value, (target, target.proxy_model)):
            return value
        return target.proxy_model(pk=value)

    def clean(self, name: str, value: Any) -> Dict[str, Any]:
        target = self.target
        retdict: Dict[str, Any] = {}
        if value is None:
            for column_name in self.get_column_names(name):
                retdict[column_name] = None
        elif isinstance(value, dict):
            for pkname in target.pknames:
                if pkname in value:
                    retdict.update(target.fields[pkname].clean(self.get_fk_field_name(name, pkname), value[pkname]))
        elif isinstance(value, BaseModel):
            for pkname in target.pknames:
                if hasattr(value, pkname):
                    retdict.update(
                        target.fields[pkname].clean(self.get_fk_field_name(name, pkname), getattr(value, pkname))
                    )
        elif len(target.pknames) == 1:
            retdict.update(
                target.fields[target.pknames[0]].clean(self.get_fk_field_name(name, target.pknames[0]), value)
            )
        else:
            raise ValueError(f"cannot handle: {value} of type {type(value)}")
        return retdict

    def modify_input(self, name: str, kwargs: Dict[str, Any]) -> None:
        if len(self.target.pknames) == 1:
            return
        to_add = {}
        for column_name in self.get_column_names(name):
            if column_name in kwargs:
                to_add[column_name] = kwargs.pop(column_name)
        # empty
        if not to_add:
            return
        if name in kwargs:
            raise ValueError("Cannot specify a fk column and the fk itself")
        kwargs[name] = to_add

    def to_model(self, field_name: str, value: Any, phase: str = "") -> Dict[str, Any]:
        """
        Like clean just for the internal input transformation. Validation happens later.
        """
        return {field_name: self.expand_relationship(value)}

    def get_fk_name(self, name: str) -> str:
        """
        Builds the fk name for the engine.

        Engines have a limitation of the foreign key being bigger than 63
        characters.

        if that happens, we need to assure it is small.
        """
        fk_name = f"fk_{self.owner.meta.tablename}_{self.target.meta.tablename}_{name}"
        if not len(fk_name) > FK_CHAR_LIMIT:
            return fk_name
        return fk_name[:FK_CHAR_LIMIT]

    def get_fk_field_name(self, name: str, pkname: str) -> str:
        target = self.target
        if len(target.pknames) == 1:
            return name
        return f"{name}_{pkname}"

    def from_fk_field_name(self, name: str, fk_field_name: str) -> str:
        target = self.target
        if len(target.pknames) == 1:
            return target.pknames[0]  # type: ignore
        return _removeprefix(fk_field_name, f"{name}_")

    def get_column_names(self, name: str) -> FrozenSet[str]:
        if not hasattr(self, "_column_names") or name != self.name:
            column_names = set()
            for column in self.get_columns(name):
                column_names.add(column.name)
            if name != self.name:
                return frozenset(column_names)
            self._column_names = frozenset(column_names)
        return self._column_names

    def get_columns(self, name: str) -> Sequence[Column]:
        target = self.target
        columns = []
        for pkname in target.pknames:
            to_field = target.fields[pkname]
            found_columns = to_field.get_columns(self.get_fk_field_name(name, pkname))
            if not self.primary_key:
                for column in found_columns:
                    column.primary_key = False
            if self.null:
                for column in found_columns:
                    column.nullable = True
            columns.extend(found_columns)
        return columns

    def get_global_constraints(self, name: str, columns: Sequence[Column]) -> Sequence[Constraint]:
        target = self.target
        return [
            ForeignKeyConstraint(
                columns,
                [f"{target.meta.tablename}.{self.from_fk_field_name(name, column.name)}" for column in columns],
                ondelete=self.on_delete,
                onupdate=self.on_update,
                name=self.get_fk_name(name),
            ),
        ]
