from __future__ import annotations

import asyncio
import inspect
import sys
from collections.abc import Awaitable
from functools import cached_property
from typing import TYPE_CHECKING, Any, ClassVar, cast

from pydantic import BaseModel, ConfigDict, Field
from pydantic.fields import FieldInfo
from pydantic.json_schema import SkipJsonSchema

from edgy.core.db.models.mixins.dump import DumpMixin
from edgy.core.marshalls.config import ConfigMarshall
from edgy.core.marshalls.fields import BaseMarshallField
from edgy.core.marshalls.metaclasses import MarshallMeta
from edgy.core.utils.sync import run_sync

if TYPE_CHECKING:
    from edgy.core.db.models.metaclasses import MetaInfo
    from edgy.core.db.models.model import Model


if sys.version_info >= (3, 11):  # pragma: no cover
    from typing import Self
else:  # pragma: no cover
    from typing_extensions import Self

# Fields to exclude when dumping the model to prevent infinite recursion or unwanted data.
excludes_marshall: set = {"instance", "_instance", "context"}


class BaseMarshall(DumpMixin, BaseModel):
    """
    Base class for all Edgy marshalls.

    Marshalls act as data transfer objects (DTOs) or serializers for Edgy models.
    They define how model data is structured and exposed, allowing for custom
    field definitions, computed properties, and controlled data serialization.

    Attributes:
        marshall_config (ClassVar[ConfigMarshall]): Configuration for the marshall,
                                                  including the associated Edgy model.
        model_config (ClassVar[ConfigDict]): Pydantic configuration for the marshall.
                                            Sets `extra="ignore"` to ignore extra fields
                                            and `arbitrary_types_allowed=True` for flexibility.
        __show_pk__ (ClassVar[bool]): If True, primary key fields will be included in serialization.
        __lazy__ (ClassVar[bool]): If True, the internal model instance is not resolved
                                   upon marshall initialization, but on first access.
        __incomplete_fields__ (ClassVar[tuple[str, ...]]): A tuple of field names that are
                                                          required but not provided during initialization.
        __custom_fields__ (ClassVar[dict[str, BaseMarshallField]]):
            A dictionary of custom (computed or sourced) fields defined in themarshall.
        _setup_used (bool): Internal flag indicating if the `_setup` method has been called.
    """

    marshall_config: ClassVar[ConfigMarshall]
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore", arbitrary_types_allowed=True)

    __show_pk__: ClassVar[bool] = False
    __lazy__: ClassVar[bool] = False
    __incomplete_fields__: ClassVar[tuple[str, ...]] = ()
    __custom_fields__: ClassVar[dict[str, BaseMarshallField]] = {}
    _setup_used: bool

    def __init__(self, instance: None | Model = None, **kwargs: Any) -> None:
        """
        Initializes a BaseMarshall instance.

        Args:
            instance (None | Model): An optional Edgy model instance to populate the marshall.
            **kwargs (Any): Arbitrary keyword arguments to initialize marshall fields.
        """
        # Determine if the marshall should be initialized lazily.
        lazy = kwargs.pop("__lazy__", type(self).__lazy__)
        data: dict = {}
        if instance is not None:
            # If an instance is provided, dump its data to populate the marshall.
            # Exclude default/unset values and internal/custom fields.
            data.update(
                instance.model_dump(
                    exclude_defaults=True,
                    exclude_unset=True,
                    exclude=excludes_marshall.union(self.__custom_fields__),
                )
            )
        # Overlay any kwargs provided directly to the marshall.
        data.update(kwargs)
        super().__init__(**data)  # Initialize Pydantic BaseModel.

        self._instance: Model | None = None
        if instance is not None:
            # If an instance was passed, assign it and resolve fields immediately.
            self.instance = instance
        elif not lazy:
            # If no instance but not lazy, set up a new instance and resolve fields.
            self._instance = self._setup()
            self._resolve_serializer(self._instance)
            self._setup_used = True  # Mark that setup was used.

    def _setup(self) -> Model:
        """
        Assembles a new Edgy model instance based on the marshall's current field values.
        This method is called when `self.instance` is accessed for the first time
        and no `instance` was provided during initialization.

        Returns:
            Model: The assembled Edgy model instance.

        Raises:
            RuntimeError: If the marshall is declared with `__incomplete_fields__`
                          and those fields are not populated for creating a new instance.
        """
        klass = type(self)
        if klass.__incomplete_fields__:
            # Prevent creating an instance if required fields are missing.
            raise RuntimeError(
                f"'{klass.__name__}' is an incomplete Marshall. "
                f"For creating new instances, it lacks following fields: [{', '.join(klass.__incomplete_fields__)}]."
            )
        model = cast(
            "Model", self.marshall_config["model"]
        )  # Get the associated Edgy model class.
        column = model.table.autoincrement_column  # Get the autoincrement PK column.
        exclude: set[str] = {*excludes_marshall}  # Start with default excluded fields.
        if column is not None:
            exclude.add(column.key)  # Exclude PK if it's autoincrement.

        # Dump marshall data to be used for the model instance.
        # Include only fields present in the model's `meta.fields` and not in `exclude`.
        data = self.model_dump(
            include=set(model.meta.fields.keys()).difference(exclude),
        )

        # Remove callable defaults that might have leaked from model fields.
        # Marshalls typically don't handle callable defaults directly.
        for k in list(data.keys()):
            if callable(data[k]):
                data.pop(k)

        # Pass internal flags to the model constructor.
        data["__show_pk__"] = self.__show_pk__
        data["__drop_extra_kwargs__"] = True
        return self.marshall_config["model"](**data)  # type: ignore

    @property
    def meta(self) -> MetaInfo:
        """
        Returns the `MetaInfo` (metadata) object of the associated Edgy model.
        """
        return cast("Model", self.marshall_config["model"]).meta

    @property
    def has_instance(self) -> bool:
        """
        Checks if an Edgy model instance is currently associated with this marshall.
        """
        return self._instance is not None

    @property
    def instance(self) -> Model:
        """
        Returns the associated Edgy model instance.
        If the instance is not yet set or resolved (due to lazy initialization),
        it calls `_setup()` to create and resolve it.
        """
        if self._instance is None:
            _instance = self._setup()
            self._resolve_serializer(_instance)
            self._instance = _instance
            self._setup_used = True  # Mark that setup was used for a lazy instance.
        return self._instance

    @instance.setter
    def instance(self, value: Model) -> None:
        """
        Sets the associated Edgy model instance. When set, it immediately resolves
        the marshall's fields from the provided instance.
        """
        self._instance = value
        self._setup_used = False  # Reset setup_used flag.
        self._resolve_serializer(instance=value)

    async def _resolve_async(self, name: str, awaitable: Awaitable) -> None:
        """
        Asynchronously resolves an awaitable and sets the result to a marshall field.

        Args:
            name (str): The name of the marshall field to set.
            awaitable (Awaitable): The awaitable object to resolve.
        """
        setattr(self, name, await awaitable)

    def _resolve_serializer(self, instance: Model) -> Self:
        """
        Resolves the marshall's custom fields by populating them with data
        from the provided Edgy model instance. Handles both direct attribute
        access and method-based field resolution, including asynchronous getters.

        Args:
            instance (Model): The Edgy model instance to extract data from.

        Returns:
            BaseMarshall: The marshall instance with its fields populated.
        """
        async_resolvers = []
        # Iterate over custom fields defined in the marshall.
        for name, field in self.__custom_fields__.items():
            if not field.__is_method__:
                # For regular fields (not method-based).
                if name in instance.pknames:
                    # Special handling for primary key attributes.
                    attribute = getattr(instance, name)
                else:
                    # Get attribute from instance, using 'source' if specified in BaseMarshallField.
                    attribute = getattr(instance, field.source or name)

                if callable(attribute):
                    # If the attribute is callable, execute it.
                    value = attribute()
                    if inspect.isawaitable(value):
                        # If the result is awaitable, add it to async_resolvers.
                        async_resolvers.append(self._resolve_async(name, value))
                        continue
                else:
                    value = attribute
                setattr(self, name, value)  # Set the field value.
            elif field.__is_method__:
                # For method-based fields.
                value = self._get_method_value(name, instance)
                if inspect.isawaitable(value):
                    # If the result of the method is awaitable, add to async_resolvers.
                    async_resolvers.append(self._resolve_async(name, value))
                    continue
                setattr(self, name, value)  # Set the field value.

        if async_resolvers:
            # If there are any async resolvers, run them synchronously.
            # This blocks until all async fields are resolved.
            run_sync(asyncio.gather(*async_resolvers))
        return self

    def _get_method_value(self, name: str, instance: Model) -> Any:
        """
        Retrieves the value for a method-based marshall field. It expects a
        method named `get_<field_name>` on the marshall instance.

        Args:
            name (str): The name of the method-based field (e.g., 'full_name' for `get_full_name`).
            instance (Model): The Edgy model instance to pass to the getter method.

        Returns:
            Any: The value returned by the getter method.
        """
        func_name: str = f"get_{name}"
        func = getattr(self, func_name)  # Get the getter method from the marshall.
        return func(instance)  # Call the getter method with the model instance.

    def _handle_primary_key(self, instance: Model) -> None:
        """
        Synchronizes the primary key fields of the marshall with those of the
        provided model instance after a save operation. This is crucial for
        newly created instances where the PK might be generated by the database.

        Args:
            instance (Model): The Edgy model instance from which to copy primary key values.
        """
        data = self.model_dump(
            include=set(instance.pknames)
        )  # Dump current PK values from marshall.

        if data:
            # Iterate over the primary key attribute names of the instance.
            for pk_attribute in instance.pknames:
                # Bypass `__setattr__` method to directly set the attribute value,
                # avoiding any potential Pydantic validation or custom logic for the PK.
                object.__setattr__(self, pk_attribute, getattr(instance, pk_attribute))

    @cached_property
    def valid_fields(self) -> dict[str, FieldInfo]:
        """
        Returns a dictionary of all Pydantic fields in the marshall that are
        not marked for exclusion. This property is cached.
        """
        return {
            k: v for k, v in type(self).model_fields.items() if not getattr(v, "exclude", True)
        }

    @cached_property
    def fields(self) -> dict[str, BaseMarshallField]:
        """
        Returns a dictionary of all custom `BaseMarshallField` instances defined
        directly on the marshall. This property is cached.
        """
        fields = {}
        for k, v in type(self).model_fields.items():
            if isinstance(v, BaseMarshallField):
                fields[k] = v
        return fields

    async def save(self) -> BaseMarshall:
        """
        Persists the associated Edgy model instance to the database.
        This method leverages Edgy's model `save()` functionality.

        If the marshall was initialized lazily (without an existing instance),
        it will attempt to save the instance created by `_setup()`.
        If the marshall was initialized with an existing instance, it will
        update that instance with the marshall's current data.

        !!! Tip
            All model and field validations are performed at the Edgy model level,
            not within the marshall.

        Returns:
            BaseMarshall: The marshall instance after the save operation,
                          with its primary key fields updated if the instance was new.
        """
        model = cast("Model", self.marshall_config["model"])
        if self._setup_used:
            # If the instance was set up via `_setup` (e.g., lazy init or new instance),
            # save the instance completely with its current state.
            instance = await self.instance.save()
        else:
            # If the instance was provided externally, update it with marshall's data.
            column = model.table.autoincrement_column
            exclude: set[str] = set()
            if column is not None:
                exclude.add(column.key)
            # Dump marshall data excluding PK and only unset values.
            data = self.model_dump(
                include=set(model.meta.fields.keys()).difference(exclude), exclude_unset=True
            )
            # Update and save the existing instance.
            instance = await self.instance.save(values=data)

        # Handle primary key synchronization for new instances or updates.
        self._handle_primary_key(instance=instance)
        return self


class Marshall(BaseMarshall, metaclass=MarshallMeta):
    """
    Concrete implementation of a Marshall, requiring the `__model__` attribute
    to be set in its `Config` or `Meta` class.
    """

    # 'context' field is excluded from JSON schema and is a dictionary.
    context: SkipJsonSchema[dict] = Field(exclude=True, default_factory=dict)

    async def save(self) -> Self:
        """
        Calls the `save` method of the `BaseMarshall`, ensuring type hinting for `Self`.
        """
        return cast("Self", await super().save())

    def __repr__(self) -> str:
        """
        Returns a developer-friendly string representation of the Marshall.
        """
        return f"<{type(self).__name__}: {self}>"

    def __str__(self) -> str:
        """
        Returns a human-readable string representation of the Marshall,
        including the name of the associated Edgy model.
        """
        return (
            f"{type(self).__name__}({cast('type[Model]', self.marshall_config['model']).__name__})"
        )
