from typing import TYPE_CHECKING, Any, ClassVar, Dict, Union

from pydantic import BaseModel, ConfigDict

from edgy.core.events import is_async_callable
from edgy.core.marshalls.config import ConfigMarshall
from edgy.core.marshalls.fields import BaseMarshallField
from edgy.core.marshalls.helpers import MarshallFieldMapping
from edgy.core.marshalls.metaclasses import MarshallMeta
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

    def _resolve_serializer(self, instance: Union["Model", None] = None) -> "BaseMarshall":
        """
        Resolve serializer fields and populate them with data from the provided instance.

        Args:
            instance (Model or None, optional): The instance to extract data from. Defaults to None.

        Returns:
            BaseMarshall: The resolved serializer instance.
        """
        # Extract fields that are instances of BaseMarshallField
        fields = {k: v for k, v in self.model_fields.items() if isinstance(v, BaseMarshallField)}

        # Dump model data excluding fields extracted above
        data = self.model_dump(exclude=set(fields.keys()))

        # Iterate over fields to populate them with data
        for name, field in fields.items():
            if field.source and field.source in data:
                setattr(self, name, getattr(instance, field.source))
            elif field.source:
                attribute = getattr(instance, field.source)

                # If attribute is callable, execute it and set the value
                if callable(attribute):
                    value = run_sync(attribute()) if is_async_callable(attribute) else attribute()
                else:
                    value = attribute
                setattr(self, name, value)
        return self

    @property
    def data(self) -> Dict[str, Any]:
        """
        Returns the data in a dictionary like
        format.
        """
        return {}

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
        data = self.model_dump(exclude={"id"})
        data["__show_pk__"] = self.__show_pk__
        instance = await self.marshall_config["model"](**data).save()  # type: ignore
        self._resolve_serializer(instance=instance)
        return self


class Marshall(BaseMarshall):
    """
    Model marshall where the `__model__` is required.
    """

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self}>"

    def __str__(self) -> str:
        return f"{self.__class__.__name__}()"
