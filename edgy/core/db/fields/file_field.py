import mimetypes
from collections.abc import Callable, Sequence
from functools import cached_property, partial
from typing import (
    TYPE_CHECKING,
    Any,
    BinaryIO,
    Literal,
    Union,
)

import orjson
import sqlalchemy
from pydantic import PlainSerializer
from pydantic.json_schema import SkipJsonSchema, WithJsonSchema

from edgy.core.db.context_vars import (
    CURRENT_MODEL_INSTANCE,
    CURRENT_PHASE,
    EXPLICIT_SPECIFIED_VALUES,
)
from edgy.core.db.fields.base import BaseCompositeField
from edgy.core.db.fields.core import BigIntegerField, BooleanField, JSONField
from edgy.core.db.fields.factories import FieldFactory
from edgy.core.db.fields.types import ColumnDefinitionModel
from edgy.core.files.base import FieldFile, File, FileStruct
from edgy.core.files.storage import storages
from edgy.exceptions import FieldDefinitionError

if TYPE_CHECKING:
    from edgy.core.db.fields.types import BaseFieldType
    from edgy.core.db.models.types import BaseModelType
    from edgy.core.files.storage import Storage

IGNORED = ["cls", "__class__", "kwargs", "generate_name_fn", "storage"]


class ConcreteFileField(BaseCompositeField):
    column_name: str = ""
    multi_process_safe: bool = True
    field_file_class: type[FieldFile]
    _generate_name_fn: (
        Callable[[Union["BaseModelType", None], File | BinaryIO, str, bool], str] | None
    ) = None
    _storage: Union[str, "Storage", None]

    @cached_property
    def storage(self) -> "Storage":
        storage = self._storage
        if not storage:
            return storages["default"]
        elif isinstance(storage, str):
            return storages[storage]
        else:
            return storage

    def modify_input(self, name: str, kwargs: dict[str, Any]) -> None:
        # we are empty
        if name not in kwargs:
            return
        extracted_names: list[str] = [name, f"{name}_storage"]
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
        instance: Union["BaseModelType", None],
        name: str,
        file: File | BinaryIO,
        direct_name: bool,
    ) -> str:
        if self._generate_name_fn is None:
            return name
        return self._generate_name_fn(instance, file, name, direct_name)

    def extract_file_instance(
        self,
        field_name: str,
        value: Any,
    ) -> FieldFile:
        phase = CURRENT_PHASE.get()
        model_instance = CURRENT_MODEL_INSTANCE.get()
        explicit_values = EXPLICIT_SPECIFIED_VALUES.get()
        # unpack when not from db
        if (
            isinstance(value, dict)
            and field_name in value
            and not isinstance(value[field_name], str)
        ):
            value = value[field_name]
        # load should refresh the state
        if (
            phase != "load"
            and model_instance is not None
            and isinstance(model_instance.__dict__.get(self.name), FieldFile)
        ):
            # use old one, when model_instance is available
            field_instance_or_value = model_instance.__dict__[self.name]
        else:
            field_instance_or_value = value
        skip_save = False
        if isinstance(field_instance_or_value, FieldFile):
            file_instance = field_instance_or_value
        else:
            # init_db, load, post_insert, post_update
            if isinstance(field_instance_or_value, dict) and isinstance(
                field_instance_or_value.get(field_name), str | type(None)
            ):
                if phase == "set":
                    raise ValueError("Cannot set dict to FileField")
                file_instance = self.field_file_class(
                    self,
                    name=field_instance_or_value[field_name] or "",
                    # can be empty string after migrations or when unset
                    # string or Storage instance are both ok for FieldFile
                    storage=field_instance_or_value.get(f"{field_name}_storage") or self.storage,
                    size=field_instance_or_value.get(f"{field_name}_size"),
                    metadata=field_instance_or_value.get(f"{field_name}_metadata", {}),
                    approved=field_instance_or_value.get(
                        f"{field_name}_approved", not self.with_approval
                    ),
                    multi_process_safe=self.multi_process_safe,
                    change_removes_approval=self.with_approval,
                    generate_name_fn=partial(self.generate_name_fn, model_instance),
                )
                skip_save = True
            else:
                # not initialized yet
                file_instance = self.field_file_class(
                    self,
                    multi_process_safe=self.multi_process_safe,
                    generate_name_fn=partial(self.generate_name_fn, model_instance),
                    storage=self.storage,
                    approved=not self.with_approval,
                    change_removes_approval=self.with_approval,
                )
        if phase in {"post_insert", "post_update"}:
            # migrations
            if value is not None:
                assert isinstance(value, dict), value
                # update after post_insert/post_update, so just update some limited values
                # which does not affect operation
                if f"{field_name}_size" in value:
                    file_instance.size = value[f"{field_name}_size"]
                if value.get(f"{field_name}_metadata") is not None:
                    file_instance.metadata = value[f"{field_name}_metadata"]
                if value.get(f"{field_name}_approved") is not None:
                    file_instance.approved = value[f"{field_name}_approved"]
        elif (
            phase == "prepare_insert"
            and explicit_values is not None
            and field_name not in explicit_values
        ):
            # revision
            file_instance.save(file_instance.to_file(), delete_old=False)
        elif value is not file_instance and not skip_save:
            if isinstance(value, dict):
                value = FileStruct.model_validate(value)
            # file creation if value is not None otherwise deletion
            file_instance.save(value, delete_old=phase == "prepare_update")
        return file_instance

    def to_model(
        self,
        field_name: str,
        value: Any,
    ) -> dict[str, Any]:
        """
        Inverse of clean. Transforms column(s) to a field for edgy.Model.
        Validation happens later.

        Args:
            field_name: the field name (can be different from name)
            value: the field value

        """
        file_instance = self.extract_file_instance(field_name, value)
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
        column_name = self.column_name or field_name
        return [
            sqlalchemy.Column(
                key=field_name,
                type_=model.column_type,
                name=column_name,
                nullable=self.get_columns_nullable(),
                **model.model_dump(by_alias=True, exclude_none=True, exclude={"column_name"}),
            ),
            sqlalchemy.Column(
                key=f"{field_name}_storage",
                name=f"{column_name}_storage",
                type_=sqlalchemy.String(length=20, collation=self.column_type.collation),
                # for migrations, default storage should be able to change without causing a new migration
                # so keep the server_default abstract.
                server_default=sqlalchemy.text("''"),
            ),
        ]

    def get_embedded_fields(
        self, name: str, fields: dict[str, "BaseFieldType"]
    ) -> dict[str, "BaseFieldType"]:
        retdict: dict[str, Any] = {}
        column_name = self.column_name or name
        # TODO: check if it works in embedded settings or embed_field is required
        if self.with_size:
            size_name = f"{name}_size"
            if size_name not in fields:
                retdict[size_name] = BigIntegerField(
                    ge=0,
                    null=self.null,
                    # we need to overwrite the method
                    get_columns_nullable=self.get_columns_nullable,
                    exclude=True,
                    read_only=True,
                    name=size_name,
                    column_name=f"{column_name}_size",
                    owner=self.owner,
                )
                retdict[size_name].metadata.append(SkipJsonSchema())
        if self.with_approval:
            approval_name = f"{name}_approved"
            if approval_name not in fields:
                retdict[approval_name] = BooleanField(
                    null=False,
                    default=False,
                    server_default=sqlalchemy.text("false"),
                    exclude=True,
                    column_name=f"{column_name}_ok",
                    name=approval_name,
                    owner=self.owner,
                )
                retdict[approval_name].metadata.append(SkipJsonSchema())
        if self.with_metadata:
            metadata_name = f"{name}_metadata"
            if metadata_name not in fields:
                retdict[metadata_name] = JSONField(
                    null=False,
                    column_name=f"{column_name}_mname",
                    name=metadata_name,
                    owner=self.owner,
                    default=dict,
                    # for migrations
                    server_default=sqlalchemy.text("'{}'"),
                )
                retdict[metadata_name].metadata.append(SkipJsonSchema())
        return retdict

    def get_composite_fields(self) -> dict[str, "BaseFieldType"]:
        field_names: list[str] = [self.name]
        if self.with_size:
            field_names.append(f"{self.name}_size")
        if self.with_approval:
            field_names.append(f"{self.name}_approved")
        if self.with_metadata:
            field_names.append(f"{self.name}_metadata")
        return {name: self.owner.meta.fields[name] for name in field_names}

    async def post_save_callback(self, value: FieldFile, is_update: bool) -> None:
        await value.execute_operation(nodelete_old=not is_update)
        # cleanup temp file
        value.close(keep_size=True)

    async def post_delete_callback(self, value: FieldFile) -> None:
        value.delete(instant=True)


def json_serializer(field_file: FieldFile) -> FileStruct | None:
    if not field_file.name:
        return None
    with field_file.open("rb") as f:
        fstruct = FileStruct(name=field_file.name, content=b"")
        fstruct.__dict__["content"] = f.read()
        return fstruct


class FileField(FieldFactory):
    field_type = Any
    field_bases = (ConcreteFileField,)

    def __new__(
        cls,
        storage: Union[str, "Storage", None] = None,
        with_size: bool = True,
        with_metadata: bool = True,
        with_approval: bool = False,
        extract_mime: bool | Literal["approved_only"] = True,
        mime_use_magic: bool = False,
        field_file_class: type[FieldFile] = FieldFile,
        generate_name_fn: Callable[[Union["BaseModelType", None], File | BinaryIO, str, bool], str]
        | None = None,
        **kwargs: Any,
    ) -> "BaseFieldType":
        kwargs = {
            **kwargs,
            **{k: v for k, v in locals().items() if k not in IGNORED},
        }
        result_field = super().__new__(
            cls, _generate_name_fn=generate_name_fn, _storage=storage, **kwargs
        )
        # result_field.metadata.append(SkipValidation())
        schema = FileStruct.model_json_schema()
        del schema["title"]
        result_field.metadata.append(WithJsonSchema(schema))
        result_field.metadata.append(
            PlainSerializer(json_serializer, return_type=FileStruct, when_used="json-unless-none")
        )
        return result_field

    @classmethod
    def validate(cls, kwargs: dict[str, Any]) -> None:
        super().validate(kwargs)
        if kwargs.get("auto_compute_server_default"):
            raise FieldDefinitionError(
                '"auto_compute_server_default" is not supported for FileField or ImageField.'
            ) from None
        kwargs["auto_compute_server_default"] = False
        if kwargs.get("server_default"):
            raise FieldDefinitionError(
                '"server_default" is not supported for FileField or ImageField.'
            ) from None
        if kwargs.get("server_onupdate"):
            raise FieldDefinitionError(
                '"server_onupdate" is not supported for FileField or ImageField.'
            ) from None
        if kwargs.get("mime_use_magic"):
            try:
                import magic  # noqa: F401  # pyright: ignore[reportMissingImports]
            except ImportError:
                raise FieldDefinitionError(
                    "python-magic library is missing. Cannot use mime_use_magic parameter"
                ) from None

    @classmethod
    def get_column_type(cls, kwargs: dict[str, Any]) -> Any:
        max_length: int | None = kwargs.get("max_length", 255)
        return (
            sqlalchemy.Text(collation=kwargs.get("collation"))
            if max_length is None
            else sqlalchemy.String(length=max_length, collation=kwargs.get("collation"))
        )

    @classmethod
    def extract_metadata(
        cls, field_obj: "BaseFieldType", field_name: str, field_file: FieldFile
    ) -> dict[str, Any]:
        data: dict[str, Any] = {}
        if field_obj.extract_mime and (
            field_file.approved or field_obj.extract_mime != "approved_only"
        ):
            if getattr(field_obj, "mime_use_magic", False):
                from magic import Magic  # pyright: ignore[reportMissingImports]

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
        value: FieldFile | str | dict,
        for_query: bool = False,
        original_fn: Any = None,
    ) -> dict[str, Any]:
        """
        Validates a value and transform it into columns which can be used for querying and saving.

        Args:
            field_name: the field name (can be different from name)
            value: the field value
        Kwargs:
            for_query: is used for querying. Should have all columns used for querying set.
        """
        assert field_obj.owner
        model_instance = CURRENT_MODEL_INSTANCE.get()
        # unpack
        if for_query:
            if (
                isinstance(value, dict)
                and field_name in value
                and isinstance(value[field_name], FieldFile | str | type(None))
            ):
                value = value[field_name]
        elif value is None:
            pass
        elif isinstance(value, dict) and field_name in value and value[field_name] is None:
            value = None
        else:
            value = file_instance = field_obj.extract_file_instance(field_name, value)
            # save in model instance, so it can be retrieved in hook
            if model_instance is not None:
                model_instance.__dict__[field_name] = file_instance
            elif file_instance.operation != "none":
                raise RuntimeError(
                    f"Cannot use QuerySet update to update FileFields ({field_name})."
                )

        # handle None
        if value is None:
            nulldict: dict[str, Any] = {
                field_name: None,
            }
            nulldict[f"{field_name}_storage"] = ""
            if not for_query:
                if field_obj.with_approval:
                    nulldict[f"{field_name}_approved"] = False
                if field_obj.with_size:
                    nulldict[f"{field_name}_size"] = None
                if field_obj.with_metadata:
                    nulldict[f"{field_name}_metadata"] = {}
            return nulldict

        if for_query:
            if isinstance(value, str):
                return {field_name: value}
            assert isinstance(value, FieldFile)
            query_dict: dict[str, Any] = {
                field_name: value.name,
            }
            query_dict[f"{field_name}_storage"] = value.storage.name
            return query_dict
        else:
            if not isinstance(value, FieldFile):
                raise ValueError(f"invalid value for for_query=False: {value} ({value!r})")
            retdict: dict[str, Any] = {
                field_name: value.name or None,
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
