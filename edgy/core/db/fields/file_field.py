import mimetypes
from functools import partial
from typing import (
    TYPE_CHECKING,
    Any,
    BinaryIO,
    Callable,
    Dict,
    List,
    Literal,
    Optional,
    Sequence,
    Type,
    Union,
    cast,
)

import orjson
import sqlalchemy

from edgy.core.db.context_vars import CURRENT_INSTANCE
from edgy.core.db.fields.base import BaseCompositeField
from edgy.core.db.fields.core import BigIntegerField, BooleanField, JSONField
from edgy.core.db.fields.factories import FieldFactory
from edgy.core.db.fields.types import ColumnDefinitionModel
from edgy.core.files.base import FieldFile, File
from edgy.core.files.storage import storages
from edgy.exceptions import FieldDefinitionError

if TYPE_CHECKING:
    from edgy.core.db.fields.types import BaseFieldType
    from edgy.core.db.models.types import BaseModelType
    from edgy.core.files.storage import Storage

IGNORED = ["cls", "__class__", "kwargs", "generate_name_fn"]


class ConcreteFileField(BaseCompositeField):
    multi_process_safe: bool = True
    field_file_class: Type[FieldFile]
    _generate_name_fn: Optional[
        Callable[[Optional["BaseModelType"], str, Union[File, BinaryIO], bool], str]
    ] = None

    def modify_input(self, name: str, kwargs: Dict[str, Any], phase: str = "") -> None:
        # we are empty
        if name not in kwargs:
            return
        extracted_names: List[str] = [name, f"{name}_storage"]
        if self.with_size:
            extracted_names.append(f"{name}_size")
        if self.with_approval:
            extracted_names.append(f"{name}_approved")
        if self.with_metadata:
            extracted_names.append(f"{name}_metadata")
        to_add = {}
        for _name in extracted_names:
            if _name in kwargs:
                to_add[_name] = kwargs.pop(_name)
        kwargs[name] = to_add

    def generate_name_fn(
        self,
        instance: Optional["BaseModelType"],
        name: str,
        file: Union[File, BinaryIO],
        direct_name: bool,
    ) -> str:
        if self._generate_name_fn is None:
            return name
        return self._generate_name_fn(instance, file, name, direct_name)

    def to_model(
        self,
        field_name: str,
        value: Any,
        phase: str = "",
    ) -> Dict[str, Any]:
        """
        Inverse of clean. Transforms column(s) to a field for a pydantic model (EdgyBaseModel).
        Validation happens later.

        Args:
            field_name: the field name (can be different from name)
            value: the field value
        Kwargs:
            phase: the phase (set, creation, ...)

        """
        instance = CURRENT_INSTANCE.get()
        if (
            phase in {"post_update", "post_insert"}
            and instance is not None
            and self.name in instance.__dict__
        ):
            # use old one
            field_instance_or_value: Any = cast(FieldFile, instance.__dict__[self.name])
        else:
            field_instance_or_value = value
        # unpack when not from db
        if isinstance(field_instance_or_value, dict) and not isinstance(
            field_instance_or_value.get(field_name), str
        ):
            field_instance_or_value = field_instance_or_value[field_name]
        if isinstance(field_instance_or_value, FieldFile):
            file_instance = field_instance_or_value
            if isinstance(value, dict):
                # update
                if value.get(f"{field_name}_size") is not None:
                    file_instance.size = value[f"{field_name}_size"]
                if value.get(f"{field_name}_metadata") is not None:
                    file_instance.metadata = value[f"{field_name}_metadata"]
                if value.get(f"{field_name}_approved") is not None:
                    file_instance.approved = value[f"{field_name}_approved"]
        else:
            # init, load, post_insert, post_update
            if isinstance(field_instance_or_value, dict):
                if phase == "set":
                    raise ValueError("Cannot set dict to FileField")
                file_instance = self.field_file_class(
                    self,
                    name=field_instance_or_value[field_name],
                    storage=field_instance_or_value.get(f"{field_name}_storage", self.storage),
                    size=field_instance_or_value.get(f"{field_name}_size"),
                    metadata=field_instance_or_value.get(f"{field_name}_metadata", {}),
                    approved=field_instance_or_value.get(
                        f"{field_name}_approved", not self.with_approval
                    ),
                    multi_process_safe=self.multi_process_safe,
                    change_removes_approval=self.with_approval,
                    generate_name_fn=partial(self.generate_name_fn, instance),
                )
            else:
                if instance is not None and self.name in instance.__dict__:
                    # use old one
                    file_instance = cast(FieldFile, instance.__dict__[self.name])
                else:
                    # not initialized yet
                    file_instance = self.field_file_class(
                        self,
                        multi_process_safe=self.multi_process_safe,
                        generate_name_fn=partial(self.generate_name_fn, instance),
                        storage=self.storage,
                        approved=not self.with_approval,
                        change_removes_approval=self.with_approval,
                    )
                # file creation if value is not None otherwise deletion
                file_instance.save(field_instance_or_value)
        retdict: Any = {field_name: file_instance}
        if self.with_size:
            retdict[f"{field_name}_size"] = file_instance.size
        if self.with_approval:
            retdict[f"{field_name}_approved"] = file_instance.approved
        if self.with_metadata:
            metadata_result: Any = file_instance.metadata
            field = self.owner.meta.fields[f"{field_name}_metadata"]
            if field.field_type is str:
                metadata_result = orjson.dumps(metadata_result).decode("utf8")
            retdict[f"{field_name}_metadata"] = metadata_result
        return retdict  # type: ignore

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
                sqlalchemy.String(length=20, collation=self.column_type.collation),
                default=self.storage.name,
            ),
        ]

    def get_embedded_fields(
        self, name: str, fields: Dict[str, "BaseFieldType"]
    ) -> Dict[str, "BaseFieldType"]:
        retdict: Dict[str, Any] = {}
        # TODO: use embed_field
        if self.with_size:
            size_name = f"{name}_size"
            if size_name not in fields:
                retdict[size_name] = BigIntegerField(
                    ge=0,
                    null=self.null,
                    exclude=True,
                    read_only=True,
                    name=size_name,
                    owner=self.owner,
                )
        if self.with_approval:
            approval_name = f"{name}_approved"
            if approval_name not in fields:
                retdict[approval_name] = BooleanField(
                    null=False,
                    default=False,
                    exclude=True,
                    column_name=f"{name}_ok",
                    name=approval_name,
                    owner=self.owner,
                )
        if self.with_metadata:
            metadata_name = f"{name}_metadata"
            if metadata_name not in fields:
                retdict[metadata_name] = JSONField(
                    null=False,
                    column_name=f"{name}_mname",
                    name=metadata_name,
                    owner=self.owner,
                    default=dict,
                )
        return retdict

    def get_composite_fields(self) -> Dict[str, "BaseFieldType"]:
        field_names: List[str] = [self.name]
        if self.with_size:
            field_names.append(f"{self.name}_size")
        if self.with_approval:
            field_names.append(f"{self.name}_approved")
        if self.with_metadata:
            field_names.append(f"{self.name}_metadata")
        return {name: self.owner.meta.fields[name] for name in field_names}

    async def post_save_callback(self, value: FieldFile, instance: "BaseModelType") -> None:
        await value.execute_operation()
        # cleanup temp file
        value.close(keep_size=True)

    async def post_delete_callback(self, value: FieldFile, instance: "BaseModelType") -> None:
        value.delete(instant=True)


class FileField(FieldFactory):
    field_type = Any
    field_bases = (ConcreteFileField,)

    def __new__(  # type: ignore
        cls,
        storage: Union[str, "Storage", None] = None,
        with_size: bool = True,
        with_metadata: bool = True,
        with_approval: bool = False,
        extract_mime: Union[bool, Literal["approved_only"]] = True,
        mime_use_magic: bool = False,
        field_file_class: Type[FieldFile] = FieldFile,
        generate_name_fn: Optional[Callable[[Optional["BaseModelType"], str], str]] = None,
        **kwargs: Any,
    ) -> "BaseFieldType":
        if not storage:
            storage = storages["default"]
        elif isinstance(storage, str):
            storage = storages[storage]

        kwargs = {
            **kwargs,
            **{k: v for k, v in locals().items() if k not in IGNORED},
        }
        return super().__new__(cls, _generate_name_fn=generate_name_fn, **kwargs)  # type: ignore

    @classmethod
    def validate(cls, kwargs: Dict[str, Any]) -> None:
        super().validate(kwargs)
        if kwargs.get("mime_use_magic"):
            try:
                import magic  # noqa: F401
            except ImportError:
                raise FieldDefinitionError(
                    "python-magic library is missing. Cannot use mime_use_magic parameter"
                ) from None

    @classmethod
    def get_column_type(cls, **kwargs: Any) -> Any:
        return sqlalchemy.String(
            length=kwargs.get("max_length", 255), collation=kwargs.get("collation", None)
        )

    @classmethod
    def extract_metadata(
        cls, field_obj: "BaseFieldType", field_name: str, field_file: FieldFile
    ) -> Dict[str, Any]:
        data: Dict[str, Any] = {}
        if field_obj.extract_mime and (
            field_file.approved or field_obj.extract_mime != "approved_only"
        ):
            if getattr(field_obj, "mime_use_magic", False):
                from magic import Magic

                magic = Magic(mime=True)
                # only open, not close, done later
                data["mime"] = magic.from_buffer(field_file.open("rb").read(2048))
            else:
                data["mime"] = mimetypes.guess_type(field_file.name)[0]
        return data

    @classmethod
    def clean(
        cls,
        field_obj: "BaseFieldType",
        field_name: str,
        value: Union[FieldFile, str, dict],
        for_query: bool = False,
        original_fn: Any = None,
    ) -> Dict[str, Any]:
        """
        Validates a value and transform it into columns which can be used for querying and saving.

        Args:
            field_name: the field name (can be different from name)
            value: the field value
        Kwargs:
            for_query: is used for querying. Should have all columns used for querying set.
        """
        assert field_obj.owner
        # unpack
        if isinstance(value, dict) and isinstance(value.get(field_name), FieldFile):
            value = value[field_name]
        assert for_query or isinstance(value, FieldFile), f"Not a FieldFile: {value!r}"
        if for_query:
            if isinstance(value, str):
                return {field_name: value}
            assert isinstance(value, FieldFile)
            query_dict: Dict[str, Any] = {
                field_name: value.name,
            }
            query_dict[f"{field_name}_storage"] = value.storage.name
            return query_dict
        else:
            if not isinstance(value, FieldFile):
                raise ValueError(f"invalid value for for_query=False: {value} ({value!r})")
            retdict: Dict[str, Any] = {
                field_name: value.name,
            }
            retdict[f"{field_name}_storage"] = value.storage.name
            if field_obj.with_approval:
                retdict[f"{field_name}_approved"] = value.approved
            if field_obj.with_size:
                retdict[f"{field_name}_size"] = value.size if value else None
            if field_obj.with_metadata:
                metadata_result: Any = (
                    cls.extract_metadata(field_obj, field_name=field_name, field_file=value)
                    if value
                    else {}
                )
                field = field_obj.owner.meta.fields[f"{field_name}_metadata"]
                # in case the field was swapped out for a text field
                if field.field_type is str:
                    metadata_result = orjson.dumps(metadata_result).decode("utf8")
                retdict[f"{field_name}_metadata"] = metadata_result
            return retdict
