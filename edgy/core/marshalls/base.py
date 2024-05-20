from typing import TYPE_CHECKING, Any, ClassVar, Dict

from pydantic import BaseModel, ConfigDict

from edgy.core.events import is_async_callable
from edgy.core.marshalls.config import ConfigMarshall
from edgy.core.marshalls.fields import BaseMarshallField
from edgy.core.marshalls.helpers import MarshallFieldMapping
from edgy.core.marshalls.metaclasses import MarshallMeta
from edgy.core.utils.functional import edgy_setattr
from edgy.core.utils.sync import run_sync

if TYPE_CHECKING:
    from edgy.core.db.models.model import Model


class BaseMarshall(BaseModel, metaclass=MarshallMeta):
    """
    Base for all the marshalls of Edgy.
    """

    marshall_config: ClassVar[ConfigMarshall]
    model_config: ClassVar[ConfigDict] = ConfigDict(arbitrary_types_allowed=True)

    __show_pk__: ClassVar[bool] = False
    __custom_fields__: ClassVar[Dict[str, BaseMarshallField]] = {}

    def __init__(self, /, **data: Any) -> None:
        super().__init__(**data)
        self._instance: "Model" = self._setup()

    def _setup(self) -> "Model":
        """
        Assemble the Marshall object with all the given details.

        Returns:
            Model or None: The assembled model instance, or None if the assembly fails.
        """
        data = self.model_dump(exclude={"id"})
        data["__show_pk__"] = self.__show_pk__
        instance: "Model" = self.marshall_config["model"](**data)  # type: ignore
        self._resolve_serializer(instance=instance)
        return instance

    @property
    def instance(self) -> "Model":
        return self._instance

    @instance.setter
    def instance(self, value: "Model") -> None:
        self._instance = value

    def _resolve_serializer(self, instance: "Model") -> "BaseMarshall":
        """
        Resolve serializer fields and populate them with data from the provided instance.

        Args:
            instance (Model or None, optional): The instance to extract data from. Defaults to None.

        Returns:
            BaseMarshall: The resolved serializer instance.
        """
        # Dump model data excluding fields extracted above
        data = self.model_dump(exclude=set(self.__custom_fields__.keys()))

        # Iterate over fields to populate them with data
        for name, field in self.__custom_fields__.items():
            if field.source and field.source in data:
                setattr(self, name, getattr(instance, field.source))
            elif field.source and not field.__is_method__:
                # For primary key exceptions
                if name == instance.pkname:
                    attribute = instance.pk
                else:
                    attribute = getattr(instance, field.source)

                # If attribute is callable, execute it and set the value
                if callable(attribute):
                    value = run_sync(attribute()) if is_async_callable(attribute) else attribute()
                else:
                    value = attribute
                setattr(self, name, value)
            elif field.__is_method__:
                value = self._get_method_value(name, instance)
                setattr(self, name, value)
        return self

    def _get_method_value(self, name: str, instance: "Model") -> Any:
        """
        Retrieve the value for a method-based field.

        Args:
            name (str): The name of the method-based field.
            instance (Model): The instance to retrieve the value from.

        Returns:
            Optional: The value retrieved from the method-based field.
        """
        func_name: str = f"get_{name}"
        func = getattr(self, func_name)
        return func(instance)

    def _handle_primary_key(self, instance: "Model") -> None:
        """
        Handles the field of a the primary key if present in the
        fields.
        """
        # Dump model data excluding fields extracted above
        data = self.model_dump(exclude=set(self.__custom_fields__.keys()))

        if instance.meta.pk_attribute in data:
            edgy_setattr(self, instance.meta.pk_attribute, instance.pk)

    def _get_fields(self) -> Dict[str, Any]:
        return self.model_fields.copy()

    @property
    def fields(self) -> MarshallFieldMapping:
        """
        Returns all the fields of the Marshall.
        """
        fields = MarshallFieldMapping(self)
        for k, v in self._get_fields().items():
            fields[k] = v
        return fields

    async def save(self) -> Any:
        """
        This save is not actually performing any specific action,
        in fact, its using the Edgy saving method and nothing else.

        We add the save here to make sure we have compatibility with
        the interface of Edgy.

        This is optional! This should only be called if you indeed
        want to persist the object in the database and have access to a
        primary key.

        !!! Tip
            All the field and model validations **are still performed**
            in the model level, not in a marshall level.
        """
        instance = await self.instance.save()
        self._handle_primary_key(instance=instance)
        return self


class Marshall(BaseMarshall):
    """
    Model marshall where the `__model__` is required.
    """

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self}>"

    def __str__(self) -> str:
        return f"{self.__class__.__name__}()"
