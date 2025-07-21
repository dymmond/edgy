from __future__ import annotations

from collections.abc import Collection
from typing import TYPE_CHECKING, Any, ClassVar, Literal, cast

from edgy.core.utils.sync import run_sync

from ..exceptions import ExcludeValue
from .context_vars import model_factory_context
from .fields import FactoryField
from .metaclasses import ModelFactoryMeta

if TYPE_CHECKING:
    from faker import Faker

    from edgy import Model
    from edgy.core.connection import Database

    from .metaclasses import MetaInfo
    from .types import FieldFactoryCallback, ModelFactoryContext

# A frozenset of argument names that should be excluded when passing
# `locals()` to other methods, particularly in `build` and `build_and_save`
# when `save=True` is used. These are typical internal or self-referential
# arguments.
DEFAULTS_WITH_SAVE = frozenset(["self", "class", "__class__", "kwargs", "save"])


class ModelFactoryContextImplementation(dict):
    """
    An implementation of the model factory context, extending dict for flexible access.

    This class serves as the concrete implementation for the `ModelFactoryContext`
    `ContextVar`. It allows attribute-style access to its dictionary items,
    particularly for the `faker` instance. It also provides a `copy` method
    to create new contexts for nested factory calls, preserving parent context
    information while allowing modifications for the current depth.
    """

    def __getattr__(self, name: str) -> Any:
        """
        Enables attribute-style access to the underlying dictionary,
        primarily for accessing `faker` methods.

        Parameters:
            name (str): The name of the attribute to retrieve.

        Returns:
            Any: The value associated with the given name, typically a Faker provider.
        """
        return getattr(self["faker"], name)

    def copy(self) -> ModelFactoryContextImplementation:
        """
        Creates a shallow copy of the current context.

        This is crucial for nested factory calls, ensuring that modifications
        to the context (e.g., incrementing depth) in a child factory do not
        affect the parent factory's context.

        Returns:
            ModelFactoryContextImplementation: A new instance of the context
                                               with a copy of the current dictionary.
        """
        return ModelFactoryContextImplementation(self)


class ModelFactory(metaclass=ModelFactoryMeta):
    """
    Base class for defining model factories in Edgy.

    `ModelFactory` is designed to streamline the creation of Edgy model instances
    with synthetic data, primarily for testing, seeding, and development purposes.
    Subclasses define how instances of a specific Edgy model should be generated,
    allowing for:
    -   Automatic data generation for model fields using the Faker library.
    -   Overriding default generated values.
    -   Excluding specific fields from generation.
    -   Configuring relationships (e.g., foreign keys, related fields).
    -   Optionally saving generated instances directly to the database.

    Each `ModelFactory` must define an inner `Meta` class that specifies the
    Edgy `model` it is associated with.

    Attributes:
        meta (ClassVar[MetaInfo]): Stores metadata about the factory, including
            the associated Edgy model and its fields.
        exclude_autoincrement (ClassVar[bool]): If `True`, fields marked as
            autoincrementing (typically primary keys) will be excluded from
            automatic data generation. Defaults to `True`.
        __defaults__ (ClassVar[dict[str, Any]]): A dictionary of default
            values for fields that will be applied if not explicitly
            provided during `ModelFactory` instantiation or `build` calls.
    """

    meta: ClassVar[MetaInfo]
    exclude_autoincrement: ClassVar[bool] = True
    __defaults__: ClassVar[dict[str, Any]] = {}

    def __init__(self, **kwargs: Any):
        """
        Initializes the ModelFactory instance.

        Any keyword arguments passed during instantiation will override
        the factory's defined `__defaults__` for the generated model.

        Parameters:
            **kwargs (Any): Initial values for the model fields. These values
                            will take precedence over any `__defaults__` defined
                            in the factory.
        """
        self.__kwargs__ = kwargs
        # Apply __defaults__ if not already present in kwargs.
        for key, value in self.__defaults__.items():
            if key not in self.__kwargs__:
                self.__kwargs__[key] = value

    @property
    def edgy_fields(self) -> dict[str, Any]:
        """
        Returns the Edgy fields of the associated model.

        This property provides convenient access to the field definitions
        of the model that this factory is configured to build.

        Returns:
            dict[str, Any]: A dictionary of field names to Edgy field instances.
        """
        return self.meta.model.meta.fields

    @property
    def model_annotations(self) -> dict[str, Any]:
        """
        Returns a dictionary mapping field names to their type annotations
        as defined in the associated Edgy model.

        Returns:
            dict[str, Any]: A dictionary of field names to their type annotations.
        """
        return {name: field.annotation for name, field in self.fields.items()}

    def to_factory_field(self) -> FactoryField:
        """
        Converts the factory into a `FactoryField` that can be used for
        relationships (e.g., `ForeignKey`).

        This method allows a `ModelFactory` to be treated as a source of
        related instances within another factory. When this `FactoryField`
        is invoked, it will call the `build` method of this factory.

        Returns:
            FactoryField: A `FactoryField` instance configured to build
                          a single instance using this factory.
        """
        # The callback for the FactoryField will call this factory's build method.
        return FactoryField(callback=lambda field, context, k: self.build(**k))

    def to_list_factory_field(self, *, min: int = 0, max: int = 10) -> FactoryField:
        """
        Converts the factory into a `FactoryField` that generates a list of
        instances for relationships like `RefForeignKey` or `RelatedField`.

        This method enables the generation of multiple related model instances.
        It creates a `FactoryField` whose callback will generate a list of
        models, with a random length between `min` and `max` (inclusive).

        Parameters:
            min (int): The minimum number of instances to generate in the list.
                       Defaults to 0.
            max (int): The maximum number of instances to generate in the list.
                       Defaults to 10.

        Returns:
            FactoryField: A `FactoryField` instance configured to build a list
                          of instances using this factory.
        """

        def callback(field: FactoryField, context: ModelFactoryContext, k: dict[str, Any]) -> Any:
            """Callback to generate a list of factory instances."""
            # Pop min/max from k, prioritizing k values.
            min_value = k.pop("min", min)
            max_value = k.pop("max", max)
            # Generate a random number of instances and build them.
            return [
                self.build(**k)
                for _ in range(context["faker"].random_int(min=min_value, max=max_value))
            ]

        return FactoryField(callback=callback)

    def build_values(
        self,
        *,
        faker: Faker | None = None,
        parameters: dict[str, dict[str, Any] | FieldFactoryCallback] | None = None,
        overwrites: dict[str, Any] | None = None,
        exclude: Collection[str] = (),
        exclude_autoincrement: bool | None = None,
        callcounts: dict[int, int] | None = None,
    ) -> dict[str, Any]:
        """
        Builds the raw dictionary of values for a model instance before Pydantic
        validation and database saving.

        This is the core logic for generating data for model fields, applying
        a hierarchy of precedence for values:
        `parameters < exclude < defaults < kwargs (from __init__) < overwrites`.

        It handles Faker callbacks, custom field callbacks, and special options
        like `randomly_unset` and `randomly_nullify`. It also manages the
        factory context for recursive factory calls.

        Parameters:
            faker (Faker | None, optional): An instance of Faker to use for
                                           data generation. If `None`, it tries
                                           to get it from the current context
                                           or the factory's meta.
            parameters (dict[str, dict[str, Any] | FieldFactoryCallback] | None, optional):
                A dictionary mapping field names to either parameters for their
                Faker methods or custom `FieldFactoryCallback` functions.
            overwrites (dict[str, Any] | None, optional): A dictionary of values
                that will explicitly override any generated or default values for
                specific fields. These have the highest precedence.
            exclude (Collection[str], optional): A collection of field names
                to exclude from generation. These fields will not be present
                in the output dictionary. Defaults to an empty tuple.
            exclude_autoincrement (bool | None, optional): If `True`, autoincrementing
                fields will be excluded. If `None`, it defaults to the factory's
                `exclude_autoincrement` or the current context's setting.
            callcounts (dict[int, int] | None, optional): A dictionary tracking
                the call counts for factory fields, used to manage recursive depth.
                If `None`, it tries to get it from the current context or the
                factory's meta.

        Returns:
            dict[str, Any]: A dictionary of generated and overridden values
                            ready to be passed to the model constructor.
        """

        # Retrieve the current factory context or initialize if none exists.
        context = model_factory_context.get(None)

        # Initialize callcounts, faker, parameters, and overwrites, prioritizing context.
        if callcounts is None:
            callcounts = context["callcounts"] if context else self.meta.callcounts
        if faker is None:
            faker = context["faker"] if context else self.meta.faker
        if not parameters:
            parameters = {}
        if not overwrites:
            overwrites = {}

        # Calculate the effective exclude_autoincrement value based on hierarchy.
        if exclude_autoincrement is None:
            exclude_autoincrement = (
                context["exclude_autoincrement"] if context else self.exclude_autoincrement
            )
        # If autoincrement exclusion is enabled, add the autoincrement column key to exclude.
        if exclude_autoincrement:
            column = self.meta.model.table.autoincrement_column
            if column is not None:
                exclude = {*exclude, column.key}

        # Start with kwargs from init, then apply overwrites.
        kwargs = self.__kwargs__.copy()
        kwargs.update(overwrites)

        values: dict[str, Any] = {}

        # Manage the factory context for nested calls.
        if context is None:
            # If no context, create a new root context.
            context = cast(
                "ModelFactoryContext",
                ModelFactoryContextImplementation(
                    faker=faker,
                    exclude_autoincrement=exclude_autoincrement,
                    depth=0,
                    callcounts=callcounts,
                ),
            )
            # Set the new context and get a token for later reset.
            token = model_factory_context.set(context)
        else:
            # If context exists, copy it and increment depth for nested calls.
            context = context.copy()
            context["depth"] += 1
            token = model_factory_context.set(context)
        try:
            # Iterate through all fields of the model to generate values.
            for name, field in self.meta.fields.items():
                # Skip fields that are already in kwargs, explicitly excluded, or marked exclude.
                if name in kwargs or name in exclude or field.exclude:
                    continue

                current_parameters_or_callback = parameters.get(name)

                # Case 1: If the parameter is a string, assume it's a Faker method name.
                if isinstance(current_parameters_or_callback, str):
                    callback_name = current_parameters_or_callback

                    # Define a lambda that calls the Faker method.
                    def _faker_callback(
                        field: FactoryField,
                        context: ModelFactoryContext,
                        params: dict[str, Any],
                        _callback_name: str = callback_name,  # Capture callback_name
                    ) -> Any:
                        return getattr(context["faker"], _callback_name)(**params)

                    current_parameters_or_callback = _faker_callback

                # Case 2: If the current_parameters_or_callback is callable (including Faker).
                try:
                    if callable(current_parameters_or_callback):
                        params = field.get_parameters(context=context)
                        # Handle 'randomly_unset' option.
                        randomly_unset = params.pop("randomly_unset", None)
                        if randomly_unset is not None and randomly_unset is not False:
                            if randomly_unset is True:
                                randomly_unset = 50
                            if faker.pybool(randomly_unset):
                                raise ExcludeValue  # Signal to exclude the field.

                        # Handle 'randomly_nullify' option.
                        randomly_nullify = params.pop("randomly_nullify", None)
                        if randomly_nullify is not None and randomly_nullify is not False:
                            if randomly_nullify is True:
                                randomly_nullify = 50
                            if faker.pybool(randomly_nullify):
                                values[name] = None  # Set value to None and continue.
                                continue
                        field.inc_callcount()  # Increment call count for the field.
                        values[name] = current_parameters_or_callback(
                            field,
                            context,
                            params,
                        )
                    else:
                        # Case 3: Parameters are a dict or None, merge with field parameters.
                        params = field.get_parameters(
                            context=context,
                            parameters=current_parameters_or_callback,
                        )
                        # Handle 'randomly_unset' option for this case.
                        randomly_unset = params.pop("randomly_unset", None)
                        if randomly_unset is not None and randomly_unset is not False:
                            if randomly_unset is True:
                                randomly_unset = 50
                            if faker.pybool(randomly_unset):
                                raise ExcludeValue  # Signal to exclude the field.

                        # Handle 'randomly_nullify' option for this case.
                        randomly_nullify = params.pop("randomly_nullify", None)
                        if randomly_nullify is not None and randomly_nullify is not False:
                            if randomly_nullify is True:
                                randomly_nullify = 50
                            if faker.pybool(randomly_nullify):
                                values[name] = None  # Set value to None and continue.
                                continue
                        field.inc_callcount()  # Increment call count for the field.
                        # Execute the field's callback with merged parameters.
                        values[name] = field(context=context, parameters=params)
                except ExcludeValue:
                    ...  # Field was explicitly excluded, continue to next field.
            values.update(kwargs)  # Apply remaining kwargs (overwrites).
        finally:
            model_factory_context.reset(token)  # Always reset the context var.
        return values

    def build(
        self,
        *,
        faker: Faker | None = None,
        parameters: dict[str, dict[str, Any] | FieldFactoryCallback] | None = None,
        overwrites: dict[str, Any] | None = None,
        exclude: Collection[str] = (),
        exclude_autoincrement: bool | None = None,
        database: Database | None | Literal[False] = None,
        schema: str | None | Literal[False] = None,
        save: bool = False,
        callcounts: dict[int, int] | None = None,
    ) -> Model:
        """
        Generates an Edgy model instance with fake data based on the factory's
        configuration.

        This method is the primary entry point for creating model instances
        without directly saving them to the database. It leverages `build_values`
        to prepare the data and then instantiates the associated Edgy model.

        Example:
            ```python
            class UserFactory(ModelFactory):
                class Meta:
                    model = User

                name = FactoryField(callback="female_name")

            user = UserFactory(name="Test User").build()
            # user.name will be "Test User", other fields will be faked.
            ```

        Parameters:
            faker (Faker | None, optional): An instance of Faker for data generation.
            parameters (dict[str, dict[str, Any] | FieldFactoryCallback] | None, optional):
                Field-specific parameters or callbacks.
            overwrites (dict[str, Any] | None, optional): Explicit values to override
                generated data.
            exclude (Collection[str], optional): Field names to exclude from generation.
            exclude_autoincrement (bool | None, optional): Whether to exclude
                autoincrementing fields.
            database (Database | None | Literal[False], optional): The database
                instance to associate with the created model. If `False`, no database
                is associated. If `None`, it defaults to the factory's internal
                `database` attribute if set.
            schema (str | None | Literal[False], optional): The database schema
                to associate with the created model. If `False`, no schema
                is associated. If `None`, it defaults to the factory's internal
                `schema` attribute if set.
            save (bool, optional): If `True`, the model instance will be built
                and then immediately saved to the database. This internally calls
                `build_and_save`. Defaults to `False`.
            callcounts (dict[int, int] | None, optional): Tracking for recursive calls.

        Returns:
            Model: A newly created Edgy model instance populated with generated data.
        """
        if save:
            # If save is True, delegate to build_and_save, passing all relevant kwargs.
            kwargs = {k: v for k, v in locals().items() if k not in DEFAULTS_WITH_SAVE}
            return cast("Model", run_sync(self.build_and_save(**kwargs)))

        # Determine the database instance to associate with the model.
        if database is None:
            database = getattr(self, "database", None)
        elif database is False:  # Explicitly setting to False clears the database.
            database = None

        # Determine the schema to associate with the model.
        if schema is None:
            schema = getattr(self, "schema", None)
        elif schema is False:  # Explicitly setting to False clears the schema.
            schema = None

        # Build the raw values dictionary.
        values = self.build_values(
            faker=faker,
            parameters=parameters,
            overwrites=overwrites,
            exclude=exclude,
            exclude_autoincrement=exclude_autoincrement,
            callcounts=callcounts,
        )
        # Instantiate the model with the generated values.
        result = self.meta.model(**values)
        # Set _db_loaded to True to prevent unnecessary database loads.
        result._db_loaded = True
        # Associate the database and schema if provided.
        if database is not None:
            result.database = database  # type: ignore
        if schema is not None:
            result.__using_schema__ = schema
        return result

    async def build_and_save(
        self,
        *,
        faker: Faker | None = None,
        parameters: dict[str, dict[str, Any] | FieldFactoryCallback] | None = None,
        overwrites: dict[str, Any] | None = None,
        exclude: Collection[str] = (),
        exclude_autoincrement: bool | None = None,
        database: Database | None | Literal[False] = None,
        schema: str | None | Literal[False] = None,
        callcounts: dict[int, int] | None = None,
    ) -> Model:
        """
        Generates an Edgy model instance with fake data and immediately saves it
        to the database.

        This asynchronous method is the recommended way to create and persist
        model instances during testing or data seeding. It first builds the model
        instance using `build` (with `save=False` to prevent recursion) and then
        calls the model's `save()` method to store it in the database.

        Example:
            ```python
            class UserFactory(ModelFactory):
                class Meta:
                    model = User
                    # Assuming User model has a 'name' field

            user = await UserFactory(name="John Doe").build_and_save()
            # A 'User' instance with name "John Doe" is created and saved to DB.
            ```

        Parameters:
            faker (Faker | None, optional): An instance of Faker for data generation.
            parameters (dict[str, dict[str, Any] | FieldFactoryCallback] | None, optional):
                Field-specific parameters or callbacks.
            overwrites (dict[str, Any] | None, optional): Explicit values to override
                generated data.
            exclude (Collection[str], optional): Field names to exclude from generation.
            exclude_autoincrement (bool | None, optional): Whether to exclude
                autoincrementing fields.
            database (Database | None | Literal[False], optional): The database
                instance to associate with the created model before saving.
            schema (str | None | Literal[False], optional): The database schema
                to associate with the created model before saving.
            callcounts (dict[int, int] | None, optional): Tracking for recursive calls.

        Returns:
            Model: The newly created and saved Edgy model instance.
        """
        # Collect relevant keyword arguments to pass to the build method.
        kwargs = {k: v for k, v in locals().items() if k not in DEFAULTS_WITH_SAVE}
        # Build the model instance without saving it immediately.
        model_instance = self.build(**kwargs, save=False)
        # Save the built model instance to the database asynchronously.
        return await model_instance.save()
