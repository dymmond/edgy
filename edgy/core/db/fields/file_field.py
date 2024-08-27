import copy
from typing import TYPE_CHECKING, Any, Dict, Union

import sqlalchemy

from edgy.core.db.fields.base import BaseField
from edgy.core.files.base import File

if TYPE_CHECKING:
    from edgy.core.db.models import Model
    from edgy.core.files.storage import Storage

CLASS_DEFAULTS = ["cls", "__class__", "kwargs"]


class Field:
    def check(self, value: Any) -> Any:
        """
        Runs the checks for the fields being validated.
        """
        return value


class FieldFactory:
    """The base for all model fields to be used with Edgy"""

    _bases = (
        Field,
        BaseField,
    )
    _type: Any = None

    def __new__(cls, *args: Any, **kwargs: Any) -> BaseField:  # type: ignore
        cls.validate(**kwargs)
        arguments = copy.deepcopy(kwargs)

        null: bool = kwargs.pop("null", False)
        name: str = kwargs.pop("name", None)
        comment: str = kwargs.pop("comment", None)
        owner = kwargs.pop("owner", None)
        secret: bool = kwargs.pop("secret", False)
        field_type = cls._type

        namespace = dict(
            __type__=field_type,
            annotation=field_type,
            name=name,
            null=null,
            comment=comment,
            owner=owner,
            format=format,
            column_type=cls.get_column_type(**arguments),
            constraints=cls.get_constraints(),
            secret=secret,
            **kwargs,
        )
        Field = type(cls.__name__, cls._bases, {})
        return Field(**namespace)  # type: ignore

    @classmethod
    def validate(cls, **kwargs: Any) -> None:  # pragma no cover
        """
        Used to validate if all required parameters on a given field type are set.
        :param kwargs: all params passed during construction
        :type kwargs: Any
        """

    @classmethod
    def get_column_type(cls, **kwargs: Any) -> Any:
        """Returns the propery column type for the field"""
        return None

    @classmethod
    def get_constraints(cls, **kwargs: Any) -> Any:
        return []


class FieldFile(File):
    def __init__(
        self, instance: Union["Model", Any], field: Any, name: Union[str, None] = None
    ) -> None:
        super().__init__(None, name)
        self._instance = instance
        self._field = field
        self._storage: "Storage" = field.storage
        self._is_committed = True

    def __eq__(self, other) -> bool:
        if hasattr(other, "name"):
            return self._name == other._name
        return self._name == other

    def __hash__(self) -> int:
        return hash(self._name)

    def _require_file(self) -> None:
        if not self:
            raise ValueError(f"The '{self._field.name}' attribute has no file associated with it.")

    def _get_file(self) -> Any:
        self._require_file()
        if getattr(self, "_file", None) is None:
            self._file = self.storage.open(self.name, "rb")
        return self._file

    def _set_file(self, file: Any) -> None:
        self._file = file

    def _del_file(self) -> None:
        del self._file

    @property
    def file(self) -> "File":
        """
        Get the file associated with this object.

        Returns:
            file: The associated file object.
        """
        return self._get_file()

    @file.setter
    def file(self, value) -> None:
        """
        Set the file associated with this object.

        Args:
            value (file): The file object to associate.
        """
        self._set_file(value)

    @file.deleter
    def file(self) -> None:
        """
        Delete the file associated with this object.
        """
        self._del_file()

    @property
    def storage(self) -> "Storage":
        return self._storage

    @property
    def instance(self) -> "Model":
        return self._instance

    @property
    def field(self) -> Any:
        return self._field

    @property
    def path(self) -> str:
        self._require_file()
        return self.storage.path(self._name)

    @property
    def url(self) -> str:
        self._require_file()
        return self.storage.url(self._name)

    @property
    def size(self) -> int:
        self._require_file()
        if not self._is_committed:
            return self.file.size
        return self.storage.size(self._name)

    def open(self, mode: Union[str, None] = None) -> "FieldFile":
        if mode is None:
            mode = "rb"
        self._require_file()
        if getattr(self, "_file", None) is None:
            self.file = self.storage.open(self._name, mode)
        else:
            self.file.open(mode)
        return self

    def save(self, name: str, content: Any, save: bool = True):
        """
        Save the file to storage and update associated model fields.

        Args:
            name (str): The name of the file.
            content: The file content.
            save (bool, optional): Whether to save the associated model instance. Defaults to True.
        """
        # Generate filename based on instance and name
        name = self.field.generate_filename(self.instance, name)

        # Save file to storage and update model fields
        self.name = self.storage.save(name, content, max_length=self.field.max_length)
        setattr(self.instance, self._field.alias, self._name)
        self._committed = True

        if save:
            self.instance.save()

    def delete(self, save: bool = True) -> None:
        """
        Delete the file associated with this object from storage.

        Args:
            save (bool, optional): Whether to save the associated model instance after deletion. Defaults to True.
        """
        if not self:
            return

        # Only close the file if it's already open
        if hasattr(self, "_file"):
            self.close()
            del self.file

        # Delete the file from storage
        self.storage.delete(self.name)

        # Update instance attributes
        self.name = None
        setattr(self.instance, self.field.alias, self.name)
        self._committed = False

        # Save the associated model instance if save is True
        if save:
            self.instance.save()

    @property
    def closed(self) -> bool:
        """
        Check if the file is closed.

        Returns:
            bool: True if the file is closed or if there is no file, False otherwise.
        """
        file = getattr(self, "_file", None)
        return file is None or file.closed

    def close(self) -> None:
        """Close the file."""
        file = getattr(self, "_file", None)
        if file is not None:
            file.close()

    def __getstate__(self) -> Dict[str, Any]:
        """
        Get the state of the object for pickling.

        Returns:
            dict: The state of the object.
        """
        return {
            "name": self.name,
            "closed": False,
            "_committed": True,
            "_file": None,
            "instance": self.instance,
            "field": self.field,
        }

    def __setstate__(self, state: Dict[str, Any]) -> None:
        """
        Set the state of the object after unpickling.

        Args:
            state (dict): The state of the object.
        """
        self.__dict__.update(state)
        self.storage = self.field.storage


class FileField(FieldFactory):
    _type: Any

    def __new__(  # type: ignore
        cls,
        verbose_name: Union[str, None] = None,
        name: Union[str, None] = None,
        storage: Union[str, None] = None,
        **kwargs: Any,
    ) -> BaseField:
        kwargs = {
            **kwargs,
            **{key: value for key, value in locals().items() if key not in CLASS_DEFAULTS},
        }

        return super().__new__(cls, **kwargs)

    @classmethod
    def get_column_type(cls, **kwargs: Any) -> Any:
        return sqlalchemy.Text()
