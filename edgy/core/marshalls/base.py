import inspect
from asyncio import gather
from collections.abc import Awaitable
from typing import TYPE_CHECKING, Any, ClassVar, Optional, cast

from pydantic import BaseModel, ConfigDict, Field

from edgy.core.marshalls.config import ConfigMarshall
from edgy.core.marshalls.fields import BaseMarshallField
from edgy.core.marshalls.metaclasses import MarshallMeta
from edgy.core.utils.sync import run_sync

if TYPE_CHECKING:
    from edgy.core.db.models.model import Model


class BaseMarshall(BaseModel, metaclass=MarshallMeta):
    """
    Base for all the marshalls of Edgy.
    """

    marshall_config: ClassVar[ConfigMarshall]
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore", arbitrary_types_allowed=True)

    __show_pk__: ClassVar[bool] = False
    __incomplete_fields__: ClassVar[tuple[str, ...]] = ()
    __custom_fields__: ClassVar[dict[str, BaseMarshallField]] = {}
    _setup_used: bool

    def __init__(self, /, **kwargs: Any) -> None:
        _instance = kwargs.pop("instance", None)
        super().__init__(**kwargs)
        self._instance: Optional[Model] = None
        if _instance is not None:
            self.instance = _instance
        elif not type(self).__incomplete_fields__:
            self._instance = self._setup()
            self._resolve_serializer(self._instance)
            self._setup_used = True

    def _setup(self) -> "Model":
        """
        Assemble the Marshall object with all the given details.

        Returns:
            Model or None: The assembled model instance, or None if the assembly fails.
        """
        klass = type(self)
        if klass.__incomplete_fields__:
            raise RuntimeError(
                f"'{klass.__name__}' is an incomplete Marshall. "
                f"For creating new instances, it lacks following fields: [{', '.join(klass.__incomplete_fields__)}]."
            )
        model = cast("Model", self.marshall_config["model"])
        column = model.table.autoincrement_column
        exclude: set[str] = set()
        if column is not None:
            exclude.add(column.key)
        data = self.model_dump(include=set(model.meta.fields.keys()).difference(exclude))
        data["__show_pk__"] = self.__show_pk__
        data["__drop_extra_kwargs__"] = True
        return self.marshall_config["model"](**data)  # type: ignore

    @property
    def instance(self) -> "Model":
        if self._instance is None:
            _instance = self._setup()
            self._resolve_serializer(_instance)
            self._instance = _instance
            self._setup_used = True
        return self._instance

    @instance.setter
    def instance(self, value: "Model") -> None:
        self._instance = value
        self._setup_used = False
        self._resolve_serializer(instance=value)

    async def _resolve_async(self, name: str, awaitable: Awaitable) -> None:
        setattr(self, name, await awaitable)

    def _resolve_serializer(self, instance: "Model") -> "BaseMarshall":
        """
        Resolve serializer fields and populate them with data from the provided instance.

        Args:
            instance (Model): The instance to extract data from.

        Returns:
            BaseMarshall: The resolved serializer instance.
        """
        # Dump model data excluding fields extracted above
        async_resolvers = []
        # Iterate over fields to populate them with data
        for name, field in self.__custom_fields__.items():
            if not field.__is_method__:
                # For primary key exceptions
                if name in instance.pknames:
                    attribute = getattr(instance, name)
                else:
                    attribute = getattr(instance, field.source or name)

                # If attribute is callable, execute it and set the value
                if callable(attribute):
                    value = attribute()
                    if inspect.isawaitable(value):
                        async_resolvers.append(self._resolve_async(name, value))
                        continue
                else:
                    value = attribute
                setattr(self, name, value)
            elif field.__is_method__:
                value = self._get_method_value(name, instance)
                setattr(self, name, value)
        if async_resolvers:
            run_sync(gather(*async_resolvers))
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
        data = self.model_dump(include=set(instance.pknames))

        # fix incomplete data
        if data:
            for pk_attribute in instance.pknames:
                # bypass __setattr__ method
                object.__setattr__(self, pk_attribute, getattr(instance, pk_attribute))

    @property
    def fields(self) -> dict[str, BaseMarshallField]:
        """
        Returns all the Marshall fields of the Marshall.
        """
        fields = {}
        # copy fields from model_fields
        for k, v in type(self).model_fields.items():
            if isinstance(v, BaseMarshallField):
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
        model = cast("Model", self.marshall_config["model"])
        if self._setup_used:
            # use defaults of Marshall, save completely
            instance = await self.instance.save()
        else:
            column = model.table.autoincrement_column
            exclude: set[str] = set()
            if column is not None:
                exclude.add(column.key)
            data = self.model_dump(include=set(model.meta.fields.keys()).difference(exclude), exclude_unset=True)
            # update without using defaults
            instance = await self.instance.save(values=data)
        self._handle_primary_key(instance=instance)
        return self


class Marshall(BaseMarshall):
    """
    Model marshall where the `__model__` is required.
    """
    context: dict = Field(exclude=True, default_factory=dict)

    def __repr__(self) -> str:
        return f"<{type(self).__name__}: {self}>"

    def __str__(self) -> str:
        return f"{type(self).__name__}()"
