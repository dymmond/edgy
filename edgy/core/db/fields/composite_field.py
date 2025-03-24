import copy
import inspect
from collections.abc import Sequence
from typing import (
    TYPE_CHECKING,
    Any,
    Optional,
    Union,
    cast,
)

from pydantic import BaseModel

from edgy.core.db.constants import ConditionalRedirect
from edgy.core.db.context_vars import MODEL_GETATTR_BEHAVIOR
from edgy.core.db.fields.base import BaseCompositeField
from edgy.core.db.fields.core import FieldFactory
from edgy.core.db.fields.types import BaseFieldType
from edgy.exceptions import FieldDefinitionError

if TYPE_CHECKING:
    from edgy.core.db.models.types import BaseModelType


class ConcreteCompositeField(BaseCompositeField):
    """
    Conrete, internal implementation of the CompositeField
    """

    prefix_embedded: str = ""
    prefix_column_name: str = ""
    unsafe_json_serialization: bool = False
    absorb_existing_fields: bool = False
    model: Union[type[BaseModel], type[ConditionalRedirect], None] = None

    def __init__(
        self,
        *,
        inner_fields: Union[
            Sequence[Union[str, tuple[str, BaseFieldType]]],
            type["BaseModelType"],
            dict[str, BaseFieldType],
        ] = (),
        **kwargs: Any,
    ) -> None:
        self.inner_field_names: list[str] = []
        self.embedded_field_defs: dict[str, BaseFieldType] = {}
        if hasattr(inner_fields, "meta"):
            kwargs.setdefault("model", inner_fields)
            kwargs.setdefault("inherit", inner_fields.meta.inherit)
            inner_fields = inner_fields.meta.fields
        if isinstance(inner_fields, dict):
            inner_fields = inner_fields.items()  # type: ignore
        owner = kwargs.get("owner")
        self.model = kwargs.pop("model", self.model)
        if self.model is not None and issubclass(self.model, BaseModel):
            kwargs["field_type"] = self.model
            kwargs["annotation"] = self.model
        super().__init__(
            # this is just a holder for real fields
            null=True,
            **kwargs,
        )
        for field in inner_fields:
            if isinstance(field, str):
                self.inner_field_names.append(field)
            elif field[1].inherit:
                # don't copy non inherit fields for excluding PKField and other surprises
                field_name = field[0]
                # for preventing suddenly invalid field names
                if self.prefix_embedded.endswith("_") and field_name.startswith("_"):
                    raise FieldDefinitionError(
                        f"_ prefixed fields are not supported: {field_name} with prefix ending with _"
                    )
                field_name = f"{self.prefix_embedded}{field_name}"
                # set field_name and owner
                field_def = field[1].embed_field(
                    self.prefix_embedded, field_name, owner=owner, parent=self
                )
                if field_def is not None:
                    field_def.exclude = True
                    self.inner_field_names.append(field_def.name)
                    self.embedded_field_defs[field_def.name] = field_def

    def translate_name(self, name: str) -> str:
        if self.prefix_embedded and name in self.embedded_field_defs:
            return name.removeprefix(self.prefix_embedded)
        return name

    def embed_field(
        self,
        prefix: str,
        new_fieldname: str,
        owner: Optional[type["BaseModelType"]] = None,
        parent: Optional[BaseFieldType] = None,
    ) -> BaseFieldType:
        field_copy = cast(
            BaseFieldType, super().embed_field(prefix, new_fieldname, owner=owner, parent=parent)
        )
        field_copy.prefix_embedded = f"{prefix}{field_copy.prefix_embedded}"
        if getattr(parent, "prefix_column_name", None):
            field_copy.prefix_column_name = (
                f"{parent.prefix_column_name}{field_copy.prefix_embedded or ''}"  # type: ignore
            )
        embedded_field_defs = field_copy.embedded_field_defs
        field_copy.inner_field_names = [
            f"{prefix}{field_name}"
            for field_name in field_copy.inner_field_names
            if field_name not in embedded_field_defs
        ]
        field_copy.embedded_field_defs = {}
        for field_name, field in embedded_field_defs.items():
            # for preventing suddenly invalid field names
            if self.prefix_embedded.endswith("_") and field_name.startswith("_"):
                raise FieldDefinitionError(
                    f"_ prefixed fields are not supported: {field_name} with prefix ending with _"
                )
            field_name = f"{prefix}{field_name}"
            field_def = field.embed_field(prefix, field_name, owner=owner, parent=field_copy)
            if field_def is not None:
                field_def.exclude = True
                field_copy.inner_field_names.append(field_def.name)
                field_copy.embedded_field_defs[field_def.name] = field_def
        return field_copy

    async def aget(
        self, instance: "BaseModelType", owner: Any = None
    ) -> Union[dict[str, Any], Any]:
        d = {}
        token = MODEL_GETATTR_BEHAVIOR.set("coro")
        try:
            for key in self.inner_field_names:
                translated_name = self.translate_name(key)
                value = getattr(instance, key)
                if inspect.isawaitable(value):
                    value = await value
                d[translated_name] = value
        finally:
            MODEL_GETATTR_BEHAVIOR.reset(token)
        if self.model is not None and self.model is not ConditionalRedirect:
            return self.model(**d)
        return d

    def __get__(self, instance: "BaseModelType", owner: Any = None) -> Union[dict[str, Any], Any]:
        assert len(self.inner_field_names) >= 1
        if self.model is ConditionalRedirect and len(self.inner_field_names) == 1:
            try:
                return getattr(instance, self.inner_field_names[0])
            except AttributeError:
                if not instance._loaded_or_deleted:
                    raise AttributeError("not loaded") from None
                return None
        if MODEL_GETATTR_BEHAVIOR.get() == "coro":
            return self.aget(instance, owner=owner)
        d = {}
        for key in self.inner_field_names:
            translated_name = self.translate_name(key)
            try:
                d[translated_name] = getattr(instance, key)
            except (AttributeError, KeyError):
                if not instance._loaded_or_deleted:
                    raise AttributeError("not loaded") from None
                pass
        if self.model is not None and self.model is not ConditionalRedirect:
            return self.model(**d)
        return d

    def clean(self, field_name: str, value: Any, for_query: bool = False) -> dict[str, Any]:
        assert len(self.inner_field_names) >= 1
        if (
            self.model is ConditionalRedirect
            and len(self.inner_field_names) == 1
            # we first only redirect both
            and not isinstance(value, (dict, BaseModel))
        ):
            field = self.owner.meta.fields[self.inner_field_names[0]]
            return field.clean(self.inner_field_names[0], value, for_query=for_query)
        return super().clean(field_name, value, for_query=for_query)

    def to_model(
        self,
        field_name: str,
        value: Any,
    ) -> dict[str, Any]:
        assert len(self.inner_field_names) >= 1
        if (
            self.model is ConditionalRedirect
            and len(self.inner_field_names) == 1
            # we first only redirect both
            and not isinstance(value, (dict, BaseModel))
        ):
            field = self.owner.meta.fields[self.inner_field_names[0]]
            return field.to_model(self.inner_field_names[0], value)
        return super().to_model(field_name, value)

    def get_embedded_fields(
        self, name: str, fields: dict[str, "BaseFieldType"]
    ) -> dict[str, "BaseFieldType"]:
        retdict = {}
        # owner is set: further down in hierarchy, or uninitialized embeddable, where the owner = model
        # owner is not set: current class
        if not self.absorb_existing_fields:
            if self.owner is None:
                duplicate_fields = set(self.embedded_field_defs.keys()).intersection(
                    {k for k, v in fields.items() if v.owner is None}
                )
                if duplicate_fields:
                    raise ValueError(f"duplicate fields: {', '.join(duplicate_fields)}")
            for field_name, field in self.embedded_field_defs.items():
                existing_field = fields.get(field_name)
                if (
                    existing_field is not None
                    and existing_field.owner is None
                    and self.owner is not None
                ):
                    continue
                # now there should be no collisions anymore
                cloned_field = copy.copy(field)
                # set to the current owner of this field, required in collision checks
                cloned_field.owner = self.owner
                cloned_field.inherit = False
                retdict[field_name] = cloned_field
            return retdict
        for field_name, field in self.embedded_field_defs.items():
            if field_name not in fields:
                cloned_field = copy.copy(field)
                # set to the current owner of this field, required in collision checks
                cloned_field.owner = self.owner
                cloned_field.inherit = False
                retdict[field_name] = cloned_field
            else:
                absorbed_field = fields[field_name]
                if not getattr(absorbed_field, "skip_absorption_check", False) and not issubclass(
                    absorbed_field.field_type, field.field_type
                ):
                    raise ValueError(
                        f'absorption failed: field "{field_name}" handle the type: {absorbed_field.field_type}, required: {field.field_type}'
                    )

        return retdict

    def get_composite_fields(self) -> dict[str, BaseFieldType]:
        return {field: self.owner.meta.fields[field] for field in self.inner_field_names}

    def is_required(self) -> bool:
        return False

    def has_default(self) -> bool:
        return False

    def __copy__(self) -> "ConcreteCompositeField":
        params = {k: v for k, v in self.__dict__.items() if k != "null"}
        copy_obj = type(self)(**params)
        copy_obj.embedded_field_defs = {
            k: copy.copy(v) for k, v in self.embedded_field_defs.items()
        }
        return copy_obj


class CompositeField(FieldFactory):
    """
    Meta field that aggregates multiple fields in a pseudo field
    """

    field_bases = (ConcreteCompositeField,)

    @classmethod
    def get_pydantic_type(cls, kwargs: dict[str, Any]) -> Any:
        """Returns the type for pydantic"""
        if "model" in kwargs:
            return kwargs.get("model")
        return dict[str, Any]

    @classmethod
    def validate(cls, kwargs: dict[str, Any]) -> None:
        inner_fields = kwargs.get("inner_fields")
        if inner_fields is not None:
            if hasattr(inner_fields, "meta"):
                kwargs.setdefault("model", inner_fields)
                inner_fields = inner_fields.meta.fields
            if isinstance(inner_fields, dict):
                inner_fields = inner_fields.items()
            elif not isinstance(inner_fields, Sequence):
                raise FieldDefinitionError("inner_fields must be a Sequence, a dict or a model")
            if not inner_fields:
                raise FieldDefinitionError("inner_fields mustn't be empty")
            inner_field_names: set[str] = set()
            for field in inner_fields:
                if isinstance(field, str):
                    if field in inner_field_names:
                        raise FieldDefinitionError(f"duplicate inner field {field}")
                else:
                    if field[0] in inner_field_names:
                        raise FieldDefinitionError(f"duplicate inner field {field}")
        model = kwargs.get("model")
        if model is not None and not isinstance(model, type):
            raise FieldDefinitionError(f"model must be type {model}")
