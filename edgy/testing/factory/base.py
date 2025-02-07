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

DEFAULTS_WITH_SAVE = frozenset(["self", "class", "__class__", "kwargs", "save"])


class ModelFactoryContextImplementation(dict):
    def __getattr__(self, name: str) -> Any:
        return getattr(self["faker"], name)

    def copy(self) -> ModelFactoryContextImplementation:
        return ModelFactoryContextImplementation(self)


class ModelFactory(metaclass=ModelFactoryMeta):
    """
    The base that must be subclassed in case of a factory
    that must be generated for a given model.
    """

    meta: ClassVar[MetaInfo]
    exclude_autoincrement: ClassVar[bool] = True
    __defaults__: ClassVar[dict[str, Any]] = {}

    def __init__(self, **kwargs: Any):
        self.__kwargs__ = kwargs
        for key, value in self.__defaults__.items():
            if key not in self.__kwargs__:
                self.__kwargs__[key] = value

    @property
    def edgy_fields(self) -> dict[str, Any]:
        return self.meta.model.meta.fields

    @property
    def model_annotations(self) -> dict[str, Any]:
        return {name: field.annotation for name, field in self.fields.items()}

    def to_factory_field(self) -> FactoryField:
        """For e.g. ForeignKey provide an instance."""
        return FactoryField(callback=lambda field, context, k: self.build(**k))

    def to_list_factory_field(self, *, min: int = 0, max: int = 10) -> FactoryField:
        """For e.g. RefForeignKey, RelatedField provide an instance list."""

        def callback(field: FactoryField, context: ModelFactoryContext, k: dict[str, Any]) -> Any:
            min_value = k.pop("min", min)
            max_value = k.pop("max", max)
            return [
                self.build(**k)
                for i in range(context["faker"].random_int(min=min_value, max=max_value))
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
    ) -> dict:
        """Underlying function to build the values which are passed into the model as kwargs"""

        # hierarchy: parameters < exclude < defaults < kwargs < overwrites
        # when using to_field the same applies to the factory used for this
        context = model_factory_context.get(None)

        if callcounts is None:
            callcounts = context["callcounts"] if context else self.meta.callcounts
        if faker is None:
            faker = context["faker"] if context else self.meta.faker
        if not parameters:
            parameters = {}
        if not overwrites:
            overwrites = {}
        # calculate the effective exclude_autoincrement value
        if exclude_autoincrement is None:
            exclude_autoincrement = (
                context["exclude_autoincrement"] if context else self.exclude_autoincrement
            )
        if exclude_autoincrement:
            column = self.meta.model.table.autoincrement_column
            if column is not None:
                exclude = {*exclude, column.key}

        kwargs = self.__kwargs__.copy()
        kwargs.update(overwrites)

        values: dict[str, Any] = {}
        if context is None:
            context = cast(
                "ModelFactoryContext",
                ModelFactoryContextImplementation(
                    faker=faker,
                    exclude_autoincrement=exclude_autoincrement,
                    depth=0,
                    callcounts=callcounts,
                ),
            )
            token = model_factory_context.set(context)
        else:
            context = context.copy()
            context["depth"] += 1
            token = model_factory_context.set(context)
        try:
            # when a field is found (include subfactory pullin)
            for name, field in self.meta.fields.items():
                if name in kwargs or name in exclude or field.exclude:
                    continue
                current_parameters_or_callback = parameters.get(name)
                # case 1: is string => make a faker callback
                if isinstance(current_parameters_or_callback, str):
                    callback_name = current_parameters_or_callback

                    def current_parameters_or_callback(
                        field: FactoryField,
                        context: ModelFactoryContext,
                        params: dict[str, Any],
                        _callback_name: str = callback_name,
                    ) -> Any:
                        return getattr(context["faker"], _callback_name)(**params)

                try:
                    # case 2: callable (also from case 1): execute it with the parameters from the field
                    if callable(current_parameters_or_callback):
                        params = field.get_parameters(context=context)
                        # special options: can simulate unset or None
                        randomly_unset = params.pop("randomly_unset", None)
                        if randomly_unset is not None and randomly_unset is not False:
                            if randomly_unset is True:
                                randomly_unset = 50
                            if faker.pybool(randomly_unset):
                                raise ExcludeValue
                        randomly_nullify = params.pop("randomly_nullify", None)
                        if randomly_nullify is not None and randomly_nullify is not False:
                            if randomly_nullify is True:
                                randomly_nullify = 50
                            if faker.pybool(randomly_nullify):
                                values[name] = None
                                continue
                        field.inc_callcount()
                        values[name] = current_parameters_or_callback(
                            field,
                            context,
                            params,
                        )
                    else:
                        # case 3: parameters are a dict: merge the parameters with the ones of the field
                        #         and execute the field callback (can be also from mappings)
                        params = field.get_parameters(
                            context=context,
                            parameters=current_parameters_or_callback,
                        )
                        # special options: can simulate unset or None
                        randomly_unset = params.pop("randomly_unset", None)
                        if randomly_unset is not None and randomly_unset is not False:
                            if randomly_unset is True:
                                randomly_unset = 50
                            if faker.pybool(randomly_unset):
                                raise ExcludeValue
                        randomly_nullify = params.pop("randomly_nullify", None)
                        if randomly_nullify is not None and randomly_nullify is not False:
                            if randomly_nullify is True:
                                randomly_nullify = 50
                            if faker.pybool(randomly_nullify):
                                values[name] = None
                                continue
                        field.inc_callcount()
                        values[name] = field(context=context, parameters=params)
                except ExcludeValue:
                    ...
            values.update(kwargs)
        finally:
            model_factory_context.reset(token)
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
        When this function is called, automacally will perform the
        generation of the model with the fake data using the
        meta.model(**self.fields) where the self.fields needs to be the
        data generated based on the model fields declared in the model.

        In the end it would be something like:

        >>> class UserFactory(ModelFactory):
        ...     class Meta:
        ...         model = User
        ...
        ...     name = FactoryField(callback="female_name")

        >>> user = UserFactory(name="XXX").build()

        The fields that are not provided will be generated using the faker library.
        """
        if save:
            kwargs = {
                **{k: v for k, v in locals().items() if k not in DEFAULTS_WITH_SAVE},
            }
            return cast("Model", run_sync(self.build_and_save(**kwargs)))

        if database is None:
            database = getattr(self, "database", None)
        elif database is False:
            database = None
        if schema is None:
            schema = getattr(self, "schema", None)
        elif schema is False:
            schema = None
        result = self.meta.model(
            **self.build_values(
                faker=faker,
                parameters=parameters,
                overwrites=overwrites,
                exclude=exclude,
                exclude_autoincrement=exclude_autoincrement,
                callcounts=callcounts,
            )
        )
        # we don't want to trigger loads.
        result._loaded_or_deleted = True
        if database is not None:
            result.database = self.database
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
        When this function is called, automacally will perform the
        generation of the model with the fake data using the
        meta.model.query.model(**self.fields).save() where the self.fields needs to be the
        data generated based on the model fields declared in the model.

        In the end it would be something like:

        >>> class UserFactory(ModelFactory):
        ...     class Meta:
        ...         model = User

        >>> user = await UserFactory(name="XXX").build_and_save()

        The fields that are not provided will be generated using the faker library.
        This function is the recommended way of creating a model instance which is saved in the database
        """
        kwargs = {
            **{k: v for k, v in locals().items() if k not in DEFAULTS_WITH_SAVE},
        }
        return await self.build(**kwargs, save=False).save()
