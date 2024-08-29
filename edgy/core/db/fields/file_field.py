from typing import TYPE_CHECKING, Any, Dict, Optional, Sequence, Union

import sqlalchemy

from edgy.core.db.fields.base import BaseCompositeField, BaseField
from edgy.core.db.fields.core import BigIntegerField
from edgy.core.db.fields.factories import FieldFactory
from edgy.core.db.fields.types import ColumnDefinitionModel
from edgy.core.files.base import FieldFile

if TYPE_CHECKING:
    from edgy import Model
    from edgy.core.db.fields.types import BaseFieldType


class ConcreteFileField(BaseCompositeField):
    def clean(self, field_name: str, value: FieldFile, for_query: bool = False) -> Dict[str, Any]:
        """
        Validates a value and transform it into columns which can be used for querying and saving.

        Args:
            field_name: the field name (can be different from name)
            value: the field value
        Kwargs:
            for_query: is used for querying. Should have all columns used for querying set.
        """
        return {}

    def to_model(
        self, field_name: str, value: Any, phase: str = "", old_value: Optional[Any] = None
    ) -> Dict[str, FieldFile]:
        """
        Inverse of clean. Transforms column(s) to a field for a pydantic model (EdgyBaseModel).
        Validation happens later.

        Args:
            field_name: the field name (can be different from name)
            value: the field value
        Kwargs:
            phase: the phase (set, creation, ...)

        """
        if isinstance(value, FieldFile):
            return {field_name: value}
        if old_value is None:
            assert phase == "creation"
            if isinstance(value, dict):
                old_value = FieldFile(self, name=value["name"], size=value.get("size"))
        return {field_name: old_value}

    def __get__(self, instance: "Model", owner: Any = None) -> FieldFile:
        if instance:
            # only or so, file is not loaded yet
            if self.name not in instance.__dict__:
                raise AttributeError()
            if instance.__dict__[self.name].instance is None:
                instance.__dict__[self.name].instance = instance
            return instance.__dict__[self.name]  # type: ignore
        raise ValueError("missing instance")

    def get_columns(self, field_name: str) -> Sequence[sqlalchemy.Column]:
        model = ColumnDefinitionModel.model_validate(self, from_attributes=True)
        return [
            sqlalchemy.Column(
                field_name,
                model.column_type,
                **model.model_dump(by_alias=True, exclude_none=True),
            ),
            sqlalchemy.Column(
                f"{field_name}_storage",
                sqlalchemy.String(length=20, collation=self.collation),
                default=self.storage,
            ),
        ]

    def get_embedded_fields(
        self, name: str, fields: Dict[str, "BaseFieldType"]
    ) -> Dict[str, "BaseField"]:
        retdict = {}
        if self.with_sizefield:
            size_name = f"{self.name}_size"
            if size_name not in fields:
                retdict[size_name] = BigIntegerField(
                    ge=0, null=self.null, exclude=True, read_only=True
                )
        return retdict

    def get_composite_fields(self) -> Dict[str, "BaseFieldType"]:
        retdict = {self.name: self}
        if self.with_sizefield:
            size_name = f"{self.name}_size"
            retdict[size_name] = self.owner.meta.fields[size_name]
        return retdict


class FileField(FieldFactory):
    _type: Any
    field_bases = (ConcreteFileField,)

    def __new__(  # type: ignore
        cls,
        storage: Union[str, None] = None,
        with_sizefield: bool = True,
        **kwargs: Any,
    ) -> BaseField:
        return super().__new__(cls, storage=storage, **kwargs)  # type: ignore

    @classmethod
    def get_column_type(cls, **kwargs: Any) -> Any:
        return sqlalchemy.String(
            length=kwargs.get("max_length", 255), collation=kwargs.get("collation", None)
        )
