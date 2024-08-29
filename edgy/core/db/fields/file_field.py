from typing import TYPE_CHECKING, Any, Dict, Optional, Sequence, Union, cast

import sqlalchemy

from edgy.core.db.fields.base import BaseCompositeField, BaseField
from edgy.core.db.fields.core import BigIntegerField
from edgy.core.db.fields.factories import FieldFactory
from edgy.core.db.fields.types import ColumnDefinitionModel
from edgy.core.files.base import FieldFile
from edgy.core.files.storage import storages

if TYPE_CHECKING:
    from edgy import Model
    from edgy.core.db.fields.types import BaseFieldType
    from edgy.core.files.storage import Storage


class ConcreteFileField(BaseCompositeField):
    def modify_input(self, name: str, kwargs: Dict[str, Any]) -> None:
        # we are initialized already or empty
        if name not in kwargs or not isinstance(kwargs[name], str):
            return
        to_add = {name: kwargs.pop(name)}
        storage_name = f"{name}_storage"
        if storage_name in kwargs:
            to_add[storage_name] = kwargs.get(storage_name)
        size_name = f"{name}_size"
        if size_name in kwargs:
            to_add[size_name] = kwargs.get(size_name)

        kwargs[name] = to_add

    def clean(self, field_name: str, value: FieldFile, for_query: bool = False) -> Dict[str, Any]:
        """
        Validates a value and transform it into columns which can be used for querying and saving.

        Args:
            field_name: the field name (can be different from name)
            value: the field value
        Kwargs:
            for_query: is used for querying. Should have all columns used for querying set.
        """
        retdict: Dict[str, Any] = {
            field_name: value.name,
        }
        if not for_query:
            retdict[f"{field_name}_storage"] = value.storage.name
            if self.with_sizefield:
                retdict[f"{field_name}_size"] = value.size if value else None
        return retdict

    def to_model(
        self, field_name: str, value: Any, phase: str = "", instance: Optional["Model"] = None
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
        # init and load
        if isinstance(value, dict):
            file_instance = FieldFile(
                self,
                name=value[field_name],
                storage=value[f"{field_name}_storage"],
                size=value.get(f"{field_name}_size"),
                generate_name_fn=self.generate_name_fn,
            )
        else:
            if instance is not None and self.name in instance.__dict__:
                # use old one
                file_instance = cast(FieldFile, instance.__dict__[self.name])
            else:
                # not initialized yet
                file_instance = FieldFile(
                    self, generate_name_fn=self.generate_name_fn, storage=self.storage
                )
                file_instance.instance = instance
            # file creation if value is not None
            file_instance.save(value)
        return {field_name: file_instance}

    def __get__(self, instance: "Model", owner: Any = None) -> FieldFile:
        if instance:
            # defer or other reason, file is not loaded yet. Trigger load.
            if self.name not in instance.__dict__:
                raise AttributeError()
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
                default=self.storage.name,
            ),
        ]

    def get_embedded_fields(
        self, name: str, fields: Dict[str, "BaseFieldType"]
    ) -> Dict[str, "BaseFieldType"]:
        retdict: Dict[str, Any] = {}
        if self.with_sizefield:
            size_name = f"{name}_size"
            if size_name not in fields:
                retdict[size_name] = BigIntegerField(
                    ge=0, null=self.null, exclude=True, read_only=True
                )
        return retdict

    def get_composite_fields(self) -> Dict[str, "BaseFieldType"]:
        retdict: Dict[str, Any] = {self.name: self}
        if self.with_sizefield:
            size_name = f"{self.name}_size"
            retdict[size_name] = self.owner.meta.fields[size_name]
        return retdict

    async def post_save_callback(self, value: FieldFile, instance: "Model") -> None:
        await value.execute_operation()


class FileField(FieldFactory):
    _type: Any
    field_bases = (ConcreteFileField,)

    def __new__(  # type: ignore
        cls,
        storage: Union[str, "Storage", None] = None,
        with_sizefield: bool = True,
        **kwargs: Any,
    ) -> BaseField:
        if not storage:
            storage = storages["default"]
        elif isinstance(storage, str):
            storage = storages[storage]

        return super().__new__(cls, storage=storage, **kwargs)  # type: ignore

    @classmethod
    def get_column_type(cls, **kwargs: Any) -> Any:
        return sqlalchemy.String(
            length=kwargs.get("max_length", 255), collation=kwargs.get("collation", None)
        )
