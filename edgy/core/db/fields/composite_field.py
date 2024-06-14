
import copy
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    List,
    Optional,
    Sequence,
    Set,
    Tuple,
    Type,
    Union,
    cast,
)

from pydantic import BaseModel

from edgy.core.db.constants import ConditionalRedirect
from edgy.core.db.fields.base import BaseCompositeField, BaseField
from edgy.core.db.fields.core import FieldFactory
from edgy.exceptions import FieldDefinitionError

if TYPE_CHECKING:
    from edgy.core.db.models.model import Model, ReflectModel


def _removeprefix(text: str, prefix: str) -> str:
    # TODO: replace with removeprefix when python3.9 is minimum
    if text.startswith(prefix):
        return text[len(prefix) :]
    else:
        return text


class ConcreteCompositeField(BaseCompositeField):
    """
    Conrete, internal implementation of the CompositeField
    """

    def __init__(self, *, inner_fields:  Union[Sequence[Union[str, Tuple[str, BaseField]]], Type["Model"], Type["ReflectModel"], Dict[str, BaseField]] =(), **kwargs: Any):
        self.inner_field_names: List[str] = []
        self.embedded_field_defs: Dict[str, BaseField] = {}
        if hasattr(inner_fields, "meta"):
            kwargs.setdefault("model", inner_fields)
            kwargs.setdefault("inherit", inner_fields.meta.inherit)
            inner_fields = inner_fields.meta.fields_mapping
        if isinstance(inner_fields, dict):
            inner_fields = inner_fields.items()  # type: ignore
        owner = kwargs.pop("owner", None)
        self.prefix_embedded: str = kwargs.pop("prefix_embedded", "")
        self.unsafe_json_serialization: bool = kwargs.pop("unsafe_json_serialization", False)
        self.absorb_existing_fields: bool = kwargs.pop("absorb_existing_fields", False)
        self.model: Optional[Union[Type[BaseModel], Type[ConditionalRedirect]]] = kwargs.pop("model", None)
        for field in inner_fields:
            if isinstance(field, str):
                self.inner_field_names.append(field)
            elif field[1].inherit:
                # don't copy non inherit fields for excluding PKField and other surprises
                field_name = field[0]
                # for preventing suddenly invalid field names
                if self.prefix_embedded.endswith("_") and field_name.startswith("_"):
                    raise FieldDefinitionError(f"_ prefixed fields are not supported: {field_name} with prefix ending with _")
                field_name = f"{self.prefix_embedded}{field_name}"
                # set field_name and owner
                # parent is None because not fully initialized
                field_def = field[1].embed_field(self.prefix_embedded, field_name, owner=owner, parent=None)
                if field_def is not None:
                    field_def.exclude = True
                    self.inner_field_names.append(field_def.name)
                    self.embedded_field_defs[field_def.name] = field_def
        return super().__init__(
            owner=owner,
            **kwargs,
        )

    def translate_name(self, name: str) -> str:
        if self.prefix_embedded and name in self.embedded_field_defs:
            # PYTHON 3.8 compatibility
            return _removeprefix(name, self.prefix_embedded)
        return name


    def embed_field(self, prefix: str, new_fieldname:str, owner: Optional[Union[Type["Model"], Type["ReflectModel"]]]=None, parent: Optional[BaseField]=None) -> BaseField:
        field_copy = cast(BaseField, super().embed_field(prefix, new_fieldname, owner=owner, parent=self))
        field_copy.prefix_embedded = f"{prefix}{field_copy.prefix_embedded}"
        embedded_field_defs = field_copy.embedded_field_defs
        field_copy.inner_field_names = [f"{prefix}{field_name}" for field_name in field_copy.inner_field_names if field_name not in embedded_field_defs]
        field_copy.embedded_field_defs = {}
        for field_name, field in embedded_field_defs.items():
            # for preventing suddenly invalid field names
            if self.prefix_embedded.endswith("_") and field_name.startswith("_"):
                raise FieldDefinitionError(f"_ prefixed fields are not supported: {field_name} with prefix ending with _")
            field_name = f"{prefix}{field_name}"
            field_def = field.embed_field(prefix, field_name, owner)
            if field_def is not None:
                field_def.exclude = True
                field_copy.inner_field_names.append(field_def.name)
                field_copy.embedded_field_defs[field_def.name] = field_def
        return field_copy

    def __get__(self, instance: "Model", owner: Any = None) -> Union[Dict[str, Any], Any]:
        assert len(self.inner_field_names) >= 1
        if self.model is ConditionalRedirect and len(self.inner_field_names) == 1:
            return getattr(instance, self.inner_field_names[0], None)
        d = {}
        for key in self.inner_field_names:
            translated_name = self.translate_name(key)
            field = instance.meta.fields_mapping.get(key)
            try:
                if field and hasattr(field, "__get__"):
                    d[translated_name] = field.__get__(instance, owner)
                else:
                    d[translated_name] = getattr(instance, key)
            except AttributeError:
                pass
        if self.model is not None and self.model is not ConditionalRedirect:
            return self.model(**d)
        return d

    def clean(self, field_name: str, value: Any, for_query: bool=False) -> Dict[str, Any]:
        assert len(self.inner_field_names) >= 1
        if (
            self.model is ConditionalRedirect
            and len(self.inner_field_names) == 1
            # we first only redirect both
            and not isinstance(value, (dict, BaseModel))
        ):
            field = self.owner.meta.fields_mapping[self.inner_field_names[0]]
            return field.clean(self.inner_field_names[0], value, for_query=for_query)
        return super().clean(field_name, value, for_query=for_query)

    def to_model(self, field_name: str, value: Any, phase: str = "") -> Dict[str, Any]:
        assert len(self.inner_field_names) >= 1
        if (
            self.model is ConditionalRedirect
            and len(self.inner_field_names) == 1
            # we first only redirect both
            and not isinstance(value, (dict, BaseModel))
        ):
            field = self.owner.meta.fields_mapping[self.inner_field_names[0]]
            return field.to_model(self.inner_field_names[0], value, phase=phase)
        return super().to_model(field_name, value, phase=phase)

    def get_embedded_fields(self, name: str, fields_mapping: Dict[str, "BaseField"]) -> Dict[str, "BaseField"]:
        retdict = {}
        # owner is set: further down in hierarchy, or uninitialized embeddable, where the owner = model
        # owner is not set: current class

        if not self.absorb_existing_fields:
            if self.owner is None:
                duplicate_fields = set(self.embedded_field_defs.keys()).intersection(  # type: ignore
                    {k for k, v in fields_mapping.items() if v.owner is None}
                )
                if duplicate_fields:
                    raise ValueError(f"duplicate fields: {', '.join(duplicate_fields)}")
            for field_name, field in self.embedded_field_defs.items():
                existing_field = fields_mapping.get(field_name, None)
                if existing_field is not None and existing_field.owner is None and self.owner is not None:  # type: ignore
                    continue  # type: ignore
                # now there should be no collisions anymore
                cloned_field = copy.copy(field)
                # set to the current owner of this field, required in collision checks
                cloned_field.owner = self.owner
                cloned_field.inherit = False
                retdict[field_name] = cloned_field
            return retdict
        for field_name, field in self.embedded_field_defs.items():
            if field_name not in fields_mapping:
                cloned_field = copy.copy(field)
                # set to the current owner of this field, required in collision checks
                cloned_field.owner = self.owner
                cloned_field.inherit = False
                retdict[field_name] = cloned_field
            else:
                absorbed_field = fields_mapping[field_name]
                if not getattr(absorbed_field, "skip_absorption_check", False) and not issubclass(
                    absorbed_field.field_type, field.field_type
                ):
                    raise ValueError(
                        f'absorption failed: field "{field_name}" handle the type: {absorbed_field.field_type}, required: {field.field_type}'
                    )
        return retdict

    def get_composite_fields(self) -> Dict[str, BaseField]:
        return {field: self.owner.meta.fields_mapping[field] for field in self.inner_field_names}

    def is_required(self) -> bool:
        return False

    def has_default(self) -> bool:
        return False


class CompositeField(FieldFactory):
    """
    Meta field that aggregates multiple fields in a pseudo field
    """

    _bases = (ConcreteCompositeField,)

    @classmethod
    def get_pydantic_type(cls, **kwargs: Any) -> Any:
        """Returns the type for pydantic"""
        if "model" in kwargs:
            return kwargs.get("model")
        return Dict[str, Any]

    @classmethod
    def validate(cls, **kwargs: Any) -> None:
        inner_fields = kwargs.get("inner_fields")
        if inner_fields is not None:
            if hasattr(inner_fields, "meta"):
                kwargs.setdefault("model", inner_fields)
                inner_fields = inner_fields.meta.fields_mapping
            if isinstance(inner_fields, dict):
                inner_fields = inner_fields.items()
            elif not isinstance(inner_fields, Sequence):
                raise FieldDefinitionError("inner_fields must be a Sequence, a dict or a model")
            if not inner_fields:
                raise FieldDefinitionError("inner_fields mustn't be empty")
            inner_field_names: Set[str] = set()
            for field in inner_fields:
                if isinstance(field, str):
                    if field in inner_field_names:
                        raise FieldDefinitionError(f"duplicate inner field {field}")
                else:
                    if field[0] in inner_field_names:
                        raise FieldDefinitionError(f"duplicate inner field {field}")
        model = kwargs.get("model", None)
        if model is not None and not isinstance(model, type):
            raise FieldDefinitionError(f"model must be type {model}")
