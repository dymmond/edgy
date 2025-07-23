from __future__ import annotations

import mimetypes
from collections.abc import Callable, Sequence
from functools import cached_property, partial
from typing import (
    TYPE_CHECKING,
    Any,
    BinaryIO,
    Literal,
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

# List of keywords to be ignored during kwargs processing in `FileField` factory.
IGNORED = ["cls", "__class__", "kwargs", "generate_name_fn", "storage"]


class ConcreteFileField(BaseCompositeField):
    """
    A concrete implementation of a file field that manages file storage and metadata.

    This field is designed to handle file uploads and retrieval, integrating with
    Edgy's model system. It includes properties for column naming, multi-process safety,
    and a customizable file generation function. It also manages associated metadata
    like file size, approval status, and custom metadata.

    Attributes:
        column_name (str): The name of the column in the database for the file path.
                           Defaults to an empty string, implying the field's name.
        multi_process_safe (bool): Indicates if file operations should be multi-process safe.
                                   Defaults to `True`.
        field_file_class (type[FieldFile]): The class to use for managing the file operations.
                                            Defaults to `FieldFile`.
        _generate_name_fn (Callable[[BaseModelType | None, File | BinaryIO, str, bool], str] | None):
            An optional function to generate the file name.
        _storage (str | Storage | None): The storage backend to use for the file.
                                         Can be a string (name of a registered storage)
                                         or a `Storage` instance. Defaults to `None`,
                                         which implies the default storage.
    """

    column_name: str = ""
    multi_process_safe: bool = True
    field_file_class: type[FieldFile]
    _generate_name_fn: Callable[[BaseModelType | None, File | BinaryIO, str, bool], str] | None = (
        None
    )
    _storage: str | Storage | None

    @cached_property
    def storage(self) -> Storage:
        """
        Retrieves the storage backend instance associated with this field.

        This property uses `cached_property` to ensure that the storage instance
        is resolved and cached only once. If `_storage` is `None`, it defaults
        to the storage named "default". If it's a string, it retrieves the
        corresponding storage from `storages`. Otherwise, it returns the
        provided `Storage` instance directly.

        Returns:
            Storage: The storage backend instance.
        """
        storage = self._storage
        if not storage:
            return storages["default"]
        elif isinstance(storage, str):
            return storages[storage]
        else:
            return storage

    def modify_input(self, name: str, kwargs: dict[str, Any]) -> None:
        """
        Modifies the input `kwargs` to group file-related attributes under a single key.

        When a file field is being initialized or updated, its associated attributes
        (like size, approval status, metadata, and storage) might be passed as
        separate keys in the `kwargs` dictionary (e.g., `my_file_size`, `my_file_approved`).
        This method extracts these related keys and consolidates them into a dictionary
        under the main field `name` key, simplifying subsequent processing.

        Args:
            name (str): The name of the file field (e.g., "my_file").
            kwargs (dict[str, Any]): The dictionary of keyword arguments to modify.
        """
        # If the main file field name is not in kwargs, there's nothing to modify.
        if name not in kwargs:
            return

        extracted_names: list[str] = [name, f"{name}_storage"]
        # Include size, approval, and metadata keys if these features are enabled.
        if self.with_size:
            extracted_names.append(f"{name}_size")
        if self.with_approval:
            extracted_names.append(f"{name}_approved")
        if self.with_metadata:
            extracted_names.append(f"{name}_metadata")

        to_add: dict[str, Any] = {}
        # Extract and remove relevant keys from kwargs, storing them in `to_add`.
        for _name in extracted_names:
            if _name in kwargs:
                to_add[_name] = kwargs.pop(_name)
        # Assign the consolidated dictionary back to the main field name.
        kwargs[name] = to_add

    def generate_name_fn(
        self,
        instance: BaseModelType | None,
        name: str,
        file: File | BinaryIO,
        direct_name: bool,
    ) -> str:
        """
        Generates the name for the stored file.

        If a custom `_generate_name_fn` is provided, it uses that function.
        Otherwise, it returns the provided `name` as is.

        Args:
            instance (BaseModelType | None): The model instance associated with the file.
            name (str): The proposed name for the file.
            file (File | BinaryIO): The file object being stored.
            direct_name (bool): Indicates if the name is directly provided.

        Returns:
            str: The generated file name.
        """
        if self._generate_name_fn is None:
            return name
        return self._generate_name_fn(instance, file, name, direct_name)

    def extract_file_instance(
        self,
        field_name: str,
        value: Any,
    ) -> FieldFile:
        """
        Extracts or initializes a `FieldFile` instance based on the current phase and value.

        This complex method manages the lifecycle of `FieldFile` objects. It
        determines whether to reuse an existing `FieldFile` from the model instance,
        initialize a new one from database-loaded data (dict of strings),
        or create a fresh `FieldFile` for new uploads or updates. It also handles
        specific logic for different operational phases like 'load', 'set',
        'post_insert', 'post_update', and 'prepare_insert'/'prepare_update'.

        Args:
            field_name (str): The name of the field.
            value (Any): The incoming value for the field, which can be a dict,
                         a `FieldFile` instance, or `None`.

        Returns:
            FieldFile: The extracted or initialized `FieldFile` instance.

        Raises:
            ValueError: If an attempt is made to set a dictionary directly to a
                        `FileField` when the phase is 'set'.
            RuntimeError: If a file operation (like save) is attempted on a
                          `FieldFile` created outside of a model instance context
                          during a query update.
        """
        phase = CURRENT_PHASE.get()
        model_instance = CURRENT_MODEL_INSTANCE.get()
        explicit_values = EXPLICIT_SPECIFIED_VALUES.get()

        # Unpack value if it's a dict containing the field_name and not already a string.
        if (
            isinstance(value, dict)
            and field_name in value
            and not isinstance(value[field_name], str)
        ):
            value = value[field_name]

        # If it's not a 'load' phase and a model instance exists with an existing FieldFile,
        # reuse the old FieldFile instance.
        if (
            phase != "load"
            and model_instance is not None
            and isinstance(model_instance.__dict__.get(self.name), FieldFile)
        ):
            field_instance_or_value = model_instance.__dict__[self.name]
        else:
            field_instance_or_value = value
        skip_save = False  # Flag to indicate if the file save operation should be skipped.

        if isinstance(field_instance_or_value, FieldFile):
            # If the value is already a FieldFile, use it directly.
            file_instance = field_instance_or_value
        else:
            # init_db, load, post_insert, post_update path
            # Initialize FieldFile from database-loaded dict or create a new one.
            if isinstance(field_instance_or_value, dict) and isinstance(
                field_instance_or_value.get(field_name), str | type(None)
            ):
                # If phase is 'set' and value is a dict, it's an invalid direct assignment.
                if phase == "set":
                    raise ValueError("Cannot set dict to FileField")
                # Initialize FieldFile from dictionary data (e.g., from DB load).
                file_instance = self.field_file_class(
                    self,
                    name=field_instance_or_value[field_name] or "",
                    # Use provided storage name or the field's default storage.
                    storage=field_instance_or_value.get(f"{field_name}_storage") or self.storage,
                    size=field_instance_or_value.get(f"{field_name}_size"),
                    metadata=field_instance_or_value.get(f"{field_name}_metadata", {}),
                    approved=field_instance_or_value.get(
                        f"{field_name}_approved", not self.with_approval
                    ),
                    multi_process_safe=self.multi_process_safe,
                    change_removes_approval=self.with_approval,
                    # Partial application of generate_name_fn with model_instance context.
                    generate_name_fn=partial(self.generate_name_fn, model_instance),
                )
                skip_save = (
                    True  # Skip immediate save as it's being initialized from existing data.
                )
            else:
                # FieldFile not initialized yet, create a new one.
                file_instance = self.field_file_class(
                    self,
                    multi_process_safe=self.multi_process_safe,
                    generate_name_fn=partial(self.generate_name_fn, model_instance),
                    storage=self.storage,
                    approved=not self.with_approval,
                    change_removes_approval=self.with_approval,
                )

        # Handle post-insert/post-update phases (e.g., for migrations).
        if phase in {"post_insert", "post_update"}:
            if value is not None:
                assert isinstance(value, dict), value
                # Update limited values without affecting file operations.
                if f"{field_name}_size" in value:
                    file_instance.size = value[f"{field_name}_size"]
                if value.get(f"{field_name}_metadata") is not None:
                    file_instance.metadata = value[f"{field_name}_metadata"]
                if value.get(f"{field_name}_approved") is not None:
                    file_instance.approved = value[f"{field_name}_approved"]
        # Handle 'prepare_insert' when explicit values are not set.
        elif (
            phase == "prepare_insert"
            and explicit_values is not None
            and field_name not in explicit_values
        ):
            # For revisions, save the file without deleting the old one.
            file_instance.save(file_instance.to_file(), delete_old=False)
        # If the value is different from the current file_instance and save is not skipped.
        elif value is not file_instance and not skip_save:
            if isinstance(value, dict):
                # If value is a dict, validate it as a FileStruct.
                value = FileStruct.model_validate(value)
            # Perform file creation or deletion based on value and phase.
            file_instance.save(value, delete_old=phase == "prepare_update")
        return file_instance

    def to_model(
        self,
        field_name: str,
        value: Any,
    ) -> dict[str, Any]:
        """
        Transforms database column values into a field for an Edgy model.

        This method is the inverse of the `clean` method. It takes raw database
        values and converts them into the appropriate `FieldFile` instance and
        its associated metadata (size, approval, custom metadata) as a dictionary
        suitable for model instantiation.

        Args:
            field_name (str): The name of the field as it appears in the model.
            value (Any): The raw value(s) from the database or input, typically a dict.

        Returns:
            dict[str, Any]: A dictionary containing the `FieldFile` instance and its
                            associated properties, keyed by field name and related names.
        """
        file_instance = self.extract_file_instance(field_name, value)
        retdict: dict[str, Any] = {field_name: file_instance}

        # Conditionally add size, approval, and metadata to the return dictionary.
        if self.with_size:
            retdict[f"{field_name}_size"] = file_instance.size
        if self.with_approval:
            retdict[f"{field_name}_approved"] = file_instance.approved
        if self.with_metadata:
            metadata_result: Any = file_instance.metadata
            # Retrieve the associated metadata field definition from the owner model.
            field = self.owner.meta.fields[f"{field_name}_metadata"]
            # If the metadata field's Pydantic type is string, serialize the metadata to JSON.
            if field.field_type is str:
                metadata_result = orjson.dumps(metadata_result).decode("utf8")
            retdict[f"{field_name}_metadata"] = metadata_result
        return retdict

    def get_columns(self, field_name: str) -> Sequence[sqlalchemy.Column]:
        """
        Generates the SQLAlchemy Column objects for the file field and its associated
        storage column.

        This method defines how the file field maps to actual database columns.
        It creates a column for the file path (based on `column_name` or `field_name`)
        and another column for the storage backend name.

        Args:
            field_name (str): The name of the field in the model.

        Returns:
            Sequence[sqlalchemy.Column]: A sequence of SQLAlchemy Column objects.
        """
        # Validate the field definition against a ColumnDefinitionModel.
        model = ColumnDefinitionModel.model_validate(self, from_attributes=True)
        column_name = self.column_name or field_name
        # TODO: check if it works in embedded settings or embed_field is required

        return [
            # Main column for the file path.
            sqlalchemy.Column(
                key=field_name,
                type_=model.column_type,
                name=column_name,
                nullable=self.get_columns_nullable(),  # Determine nullability based on field settings.
                **model.model_dump(by_alias=True, exclude_none=True, exclude={"column_name"}),
            ),
            # Column for storing the storage backend name.
            sqlalchemy.Column(
                key=f"{field_name}_storage",
                name=f"{column_name}_storage",
                type_=sqlalchemy.String(length=20, collation=self.column_type.collation),
                # Use an empty string as server default for migration flexibility.
                server_default=sqlalchemy.text("''"),
            ),
        ]

    def get_embedded_fields(
        self, name: str, fields: dict[str, BaseFieldType]
    ) -> dict[str, BaseFieldType]:
        """
        Generates and returns embedded fields (size, approval, metadata) associated
        with the main file field.

        These fields are "embedded" in the sense that they are conceptually part
        of the file field but might map to separate columns in the database and
        are often excluded from direct JSON schema generation. This method
        dynamically creates these auxiliary fields if they are enabled and not
        already defined in the model's fields.

        Args:
            name (str): The name of the main file field.
            fields (dict[str, BaseFieldType]): The existing fields of the model,
                                              used to check for existing definitions.

        Returns:
            dict[str, BaseFieldType]: A dictionary of dynamically created embedded fields.
        """
        retdict: dict[str, Any] = {}
        column_name = self.column_name or name

        # Add a BigIntegerField for file size if `with_size` is True.
        if self.with_size:
            size_name = f"{name}_size"
            if size_name not in fields:  # Only add if not already present.
                retdict[size_name] = BigIntegerField(
                    ge=0,  # Greater than or equal to 0.
                    null=self.null,
                    get_columns_nullable=self.get_columns_nullable,  # Inherit nullability.
                    exclude=True,  # Exclude from direct model dict.
                    read_only=True,  # Read-only field.
                    name=size_name,
                    column_name=f"{column_name}_size",
                    owner=self.owner,
                )
                retdict[size_name].metadata.append(SkipJsonSchema())  # Skip JSON schema.

        # Add a BooleanField for file approval if `with_approval` is True.
        if self.with_approval:
            approval_name = f"{name}_approved"
            if approval_name not in fields:
                retdict[approval_name] = BooleanField(
                    null=False,
                    default=False,
                    server_default=sqlalchemy.text("false"),  # Default to false in DB.
                    exclude=True,
                    column_name=f"{column_name}_ok",
                    name=approval_name,
                    owner=self.owner,
                )
                retdict[approval_name].metadata.append(SkipJsonSchema())

        # Add a JSONField for custom metadata if `with_metadata` is True.
        if self.with_metadata:
            metadata_name = f"{name}_metadata"
            if metadata_name not in fields:
                retdict[metadata_name] = JSONField(
                    null=False,
                    column_name=f"{column_name}_mname",  # Renamed in db because of name length restrictions
                    name=metadata_name,
                    owner=self.owner,
                    default=dict,  # Default to an empty dictionary.
                    server_default=sqlalchemy.text("'{}'"),  # Default to empty JSON object in DB.
                )
                retdict[metadata_name].metadata.append(SkipJsonSchema())
        return retdict

    def get_composite_fields(self) -> dict[str, BaseFieldType]:
        """
        Returns a dictionary of all composite fields associated with this file field.

        This includes the main file field itself and any enabled embedded fields
        (size, approval, metadata). It retrieves the actual field objects from
        the owner model's metadata.

        Returns:
            dict[str, BaseFieldType]: A dictionary mapping field names to their
                                      corresponding `BaseFieldType` instances.
        """
        field_names: list[str] = [self.name]
        if self.with_size:
            field_names.append(f"{self.name}_size")
        if self.with_approval:
            field_names.append(f"{self.name}_approved")
        if self.with_metadata:
            field_names.append(f"{self.name}_metadata")
        return {name: self.owner.meta.fields[name] for name in field_names}

    async def post_save_callback(self, value: FieldFile, is_update: bool) -> None:
        """
        Callback executed after a model instance containing this field is saved.

        This method triggers the `execute_operation` on the `FieldFile` instance,
        which handles the actual file saving or deletion logic. It also ensures
        that any temporary files are cleaned up.

        Args:
            value (FieldFile): The `FieldFile` instance associated with the field.
            is_update (bool): `True` if the save operation was an update, `False` for an insert.
        """
        # Execute the file operation (save/delete). `nodelete_old` ensures old file
        # is deleted only on update if specified.
        await value.execute_operation(nodelete_old=not is_update)
        # cleanup temp file, keeping its size for later use.
        value.close(keep_size=True)

    async def post_delete_callback(self, value: FieldFile) -> None:
        """
        Callback executed after a model instance containing this field is deleted.

        This method triggers the `delete` operation on the `FieldFile` instance,
        which handles the immediate deletion of the associated file from storage.

        Args:
            value (FieldFile): The `FieldFile` instance associated with the field.
        """
        value.delete(instant=True)


def json_serializer(field_file: FieldFile) -> FileStruct | None:
    """
    Custom JSON serializer for `FieldFile` instances.

    This function is used by Pydantic's `PlainSerializer` to convert a `FieldFile`
    into a `FileStruct` suitable for JSON serialization. It reads the file content
    into the `content` attribute of the `FileStruct`. If the `field_file.name`
    is empty, it returns `None`.

    Args:
        field_file (FieldFile): The `FieldFile` instance to serialize.

    Returns:
        FileStruct | None: A `FileStruct` containing the file's name and content,
                           or `None` if the file name is empty.
    """
    if not field_file.name:
        return None
    # Open the file in binary read mode.
    with field_file.open("rb") as f:
        # Create a FileStruct, initially with empty content.
        fstruct = FileStruct(name=field_file.name, content=b"")
        # Manually set the content to avoid re-validation by Pydantic upon creation.
        fstruct.__dict__["content"] = f.read()
        return fstruct


class FileField(FieldFactory):
    """
    A factory for creating `FileField` instances, which manage file uploads and storage.

    This factory extends `FieldFactory` to provide a convenient way to define
    file fields in Edgy models. It allows configuration of storage backends,
    whether to track file size, metadata, and approval status, and provides
    custom validation logic specific to file fields.
    """

    field_type: Any = Any  # The Pydantic type for the file field, usually Any.
    field_bases: tuple = (ConcreteFileField,)  # The base concrete field class.

    def __new__(
        cls,
        storage: str | Storage | None = None,
        with_size: bool = True,
        with_metadata: bool = True,
        with_approval: bool = False,
        extract_mime: bool | Literal["approved_only"] = True,
        mime_use_magic: bool = False,
        field_file_class: type[FieldFile] = FieldFile,
        generate_name_fn: (
            Callable[[BaseModelType | None, File | BinaryIO, str, bool], str] | None
        ) = None,
        **kwargs: Any,
    ) -> BaseFieldType:
        """
        Creates a new `FileField` instance, processing file-specific arguments.

        This method combines the `FileField`-specific arguments with generic
        `kwargs`, validates them, and then delegates to the `FieldFactory`'s
        `__new__` method to build the base field. It also adds Pydantic
        JSON schema and serializer metadata.

        Args:
            storage (str | Storage | None): The storage backend to use.
            with_size (bool): Whether to store file size. Defaults to `True`.
            with_metadata (bool): Whether to store custom metadata. Defaults to `True`.
            with_approval (bool): Whether files require approval. Defaults to `False`.
            extract_mime (bool | Literal["approved_only"]): Whether to extract MIME type.
                                                           Can be `True`, `False`, or
                                                           `"approved_only"`. Defaults to `True`.
            mime_use_magic (bool): Whether to use `python-magic` for MIME type detection.
                                   Defaults to `False`.
            field_file_class (type[FieldFile]): Custom `FieldFile` class to use.
            generate_name_fn (Callable[[BaseModelType | None, File | BinaryIO, str, bool], str] | None):
                Custom function for generating file names.
            **kwargs (Any): Additional keyword arguments for the field.

        Returns:
            BaseFieldType: The constructed `FileField` instance.
        """
        # Combine local variables (FileField specific args) with general kwargs,
        # excluding ignored keywords.
        kwargs = {
            **kwargs,
            **{k: v for k, v in locals().items() if k not in IGNORED},
        }
        # Call the parent FieldFactory's __new__ to build the base field.
        result_field = super().__new__(
            cls, _generate_name_fn=generate_name_fn, _storage=storage, **kwargs
        )
        # Add Pydantic JSON schema for FileStruct representation.
        schema = FileStruct.model_json_schema()
        del schema["title"]  # Remove default Pydantic title.
        del schema["description"]  # Remove default Pydantic desscription.
        result_field.metadata.append(WithJsonSchema(schema))
        # Add a PlainSerializer for custom JSON serialization.
        result_field.metadata.append(
            PlainSerializer(json_serializer, return_type=FileStruct, when_used="json-unless-none")
        )
        return result_field

    @classmethod
    def validate(cls, kwargs: dict[str, Any]) -> None:
        """
        Performs validation specific to `FileField` instances.

        This method overrides the parent `validate` method to enforce rules
        that are particular to file fields. It disallows `auto_compute_server_default`,
        `server_default`, and `server_onupdate` as they are not applicable or
        can lead to issues with file management. It also checks for the presence
        of the `python-magic` library if `mime_use_magic` is enabled.

        Args:
            kwargs (dict[str, Any]): The dictionary of keyword arguments passed
                                     during field construction.

        Raises:
            FieldDefinitionError: If any validation rule is violated.
        """
        super().validate(kwargs)
        # Disallow auto_compute_server_default.
        if kwargs.get("auto_compute_server_default"):
            raise FieldDefinitionError(
                '"auto_compute_server_default" is not supported for FileField or ImageField.'
            ) from None
        kwargs["auto_compute_server_default"] = False  # Explicitly set to False.
        # Disallow server_default.
        if kwargs.get("server_default"):
            raise FieldDefinitionError(
                '"server_default" is not supported for FileField or ImageField.'
            ) from None
        # Disallow server_onupdate.
        if kwargs.get("server_onupdate"):
            raise FieldDefinitionError(
                '"server_onupdate" is not supported for FileField or ImageField.'
            ) from None
        # Check for python-magic if mime_use_magic is enabled.
        if kwargs.get("mime_use_magic"):
            try:
                import magic  # noqa: F401
            except ImportError:
                raise FieldDefinitionError(
                    "python-magic library is missing. Cannot use mime_use_magic parameter"
                ) from None

    @classmethod
    def get_column_type(cls, kwargs: dict[str, Any]) -> Any:
        """
        Determines the SQLAlchemy column type for the file path.

        This method returns either `sqlalchemy.Text` if `max_length` is `None`
        (indicating a long text field for paths), or `sqlalchemy.String` with
        a specified `max_length`.

        Args:
            kwargs (dict[str, Any]): Keyword arguments provided during field creation,
                                     potentially including `max_length` and `collation`.

        Returns:
            Any: The appropriate SQLAlchemy column type.
        """
        max_length: int | None = kwargs.get("max_length", 255)
        return (
            sqlalchemy.Text(collation=kwargs.get("collation"))
            if max_length is None
            else sqlalchemy.String(length=max_length, collation=kwargs.get("collation"))
        )

    @classmethod
    def extract_metadata(
        cls, field_obj: BaseFieldType, field_name: str, field_file: FieldFile
    ) -> dict[str, Any]:
        """
        Extracts metadata (like MIME type) from the file.

        This method extracts the MIME type based on `extract_mime` and
        `mime_use_magic` settings. If `mime_use_magic` is `True`, it uses
        `python-magic` to detect the MIME type from the file's buffer.
        Otherwise, it falls back to `mimetypes.guess_type`.

        Args:
            field_obj (BaseFieldType): The field object itself.
            field_name (str): The name of the field.
            field_file (FieldFile): The `FieldFile` instance from which to extract metadata.

        Returns:
            dict[str, Any]: A dictionary containing extracted metadata, e.g., `{"mime": "image/jpeg"}`.
        """
        data: dict[str, Any] = {}
        # Check if MIME extraction is enabled and if the file is approved (if required).
        if field_obj.extract_mime and (
            field_file.approved or field_obj.extract_mime != "approved_only"
        ):
            if getattr(field_obj, "mime_use_magic", False):
                # Use python-magic for more accurate MIME type detection.
                from magic import Magic  # pyright: ignore[reportMissingImports]

                magic = Magic(mime=True)
                # Read a buffer from the file to detect MIME type.
                data["mime"] = magic.from_buffer(field_file.open("rb").read(2048))
            else:
                # Fallback to mimetypes.guess_type based on file name.
                data["mime"] = mimetypes.guess_type(field_file.name)[0]
        return data

    @classmethod
    def clean(
        cls,
        field_obj: BaseFieldType,
        field_name: str,
        value: FieldFile | str | dict | bool | None,
        for_query: bool = False,
        original_fn: Any = None,
    ) -> dict[str, Any]:
        """
        Validates a value for the file field and transforms it into columns
        suitable for querying and saving.

        This method is a critical part of the data pipeline for file fields.
        It handles different input types (raw strings, dictionaries, `FieldFile` instances)
        and transforms them into a consistent dictionary format that can be used
        to update database columns. It differentiates between `for_query` operations
        (which only need the file path and storage) and regular save operations
        (which need all associated metadata).

        Args:
            field_obj (BaseFieldType): The field object itself.
            field_name (str): The name of the field.
            value (FieldFile | str | dict): The input value for the field.
            for_query (bool): If `True`, the cleaning is for a query (e.g., filtering).
                              Defaults to `False`.
            original_fn (Any): The original function, if any, that was called.
                               Defaults to `None`.

        Returns:
            dict[str, Any]: A dictionary representing the column values for the field.

        Raises:
            AssertionError: If `field_obj.owner` is not set when expected.
            ValueError: If an invalid value type is provided for non-query operations.
            RuntimeError: If attempting a file operation on a `FieldFile`
                          not associated with a model instance during a query update.
        """
        assert field_obj.owner  # Ensure the field has an owner model.
        model_instance = CURRENT_MODEL_INSTANCE.get()

        # Unpack the value if it's a dictionary containing the field and is for a query.
        if for_query:
            if (
                isinstance(value, dict)
                and field_name in value
                and isinstance(value[field_name], FieldFile | str | type(None))
            ):
                value = value[field_name]
        # Handle None values.
        elif value is None:
            pass
        elif isinstance(value, dict) and field_name in value and value[field_name] is None:
            value = None
        else:
            # Extract or initialize the FieldFile instance.
            value = file_instance = field_obj.extract_file_instance(field_name, value)
            # Store the FieldFile instance in the model's __dict__ for later retrieval by hooks.
            if model_instance is not None:
                model_instance.__dict__[field_name] = file_instance
            # If a file operation is pending without a model instance, raise an error.
            elif file_instance.operation != "none":
                raise RuntimeError(
                    f"Cannot use QuerySet update to update FileFields ({field_name})."
                )

        # Process None value.
        if value is None:
            nulldict: dict[str, Any] = {
                field_name: None,
            }
            nulldict[f"{field_name}_storage"] = ""
            if not for_query:
                # For non-query operations, set associated metadata fields to their null/default values.
                if field_obj.with_approval:
                    nulldict[f"{field_name}_approved"] = False
                if field_obj.with_size:
                    nulldict[f"{field_name}_size"] = None
                if field_obj.with_metadata:
                    nulldict[f"{field_name}_metadata"] = {}
            return nulldict

        # Process for query operations.
        if for_query:
            if field_name.endswith("__isnull") or field_name.endswith("__isempty"):
                assert isinstance(value, bool)
                return {field_name: value}
            if isinstance(value, str):
                return {field_name: value}
            assert isinstance(value, FieldFile)
            query_dict: dict[str, Any] = {
                field_name: value.name,
            }
            query_dict[f"{field_name}_storage"] = value.storage.name
            return query_dict
        else:
            # Process for non-query (save) operations.
            if not isinstance(value, FieldFile):
                raise ValueError(f"invalid value for for_query=False: {value} ({value!r})")
            retdict: dict[str, Any] = {
                field_name: value.name or None,  # File name or None if empty.
            }
            retdict[f"{field_name}_storage"] = value.storage.name
            if field_obj.with_approval:
                retdict[f"{field_name}_approved"] = value.approved
            if field_obj.with_size:
                retdict[f"{field_name}_size"] = value.size if value else None
            if field_obj.with_metadata:
                # Extract metadata if `with_metadata` is true.
                metadata_result: Any = (
                    cls.extract_metadata(field_obj, field_name=field_name, field_file=value)
                    if value
                    else {}
                )
                field = field_obj.owner.meta.fields[f"{field_name}_metadata"]
                # If the metadata field is stored as a string, serialize to JSON.
                if field.field_type is str:
                    metadata_result = orjson.dumps(metadata_result).decode("utf8")
                retdict[f"{field_name}_metadata"] = metadata_result
            return retdict
