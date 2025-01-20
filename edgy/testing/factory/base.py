from __future__ import annotations

from collections.abc import Container
from typing import TYPE_CHECKING, Any, Literal

from edgy import Model

from ..exceptions import ExcludeValue
from .fields import FactoryField
from .metaclasses import ModelFactoryMeta

if TYPE_CHECKING:
    from faker import Faker

    from edgy.core.connection import Database

    from .metaclasses import MetaInfo
    from .types import FactoryCallback


class ModelFactory(metaclass=ModelFactoryMeta):
    """
    The base that must be subclassed in case of a factory
    that must be generated for a given model.
    """

    meta: MetaInfo

    def __init__(self, **kwargs: Any):
        self.__kwargs__ = kwargs

    @property
    def edgy_fields(self) -> dict[str, Any]:
        return self.meta.model.meta.fields

    @property
    def model_annotations(self) -> dict[str, Any]:
        return {name: field.annotation for name, field in self.fields.items()}

    @classmethod
    def to_factory_field(cls) -> FactoryField:
        """For e.g. ForeignKey provide an instance."""
        instance = cls()
        return FactoryField(callback=lambda field, faker, k: instance.build(faker=faker, **k))

    @classmethod
    def to_list_factory_field(cls, *, min: int = 0, max: int = 100) -> FactoryField:
        """For e.g. RefForeignKey, RelatedField provide an instance list."""
        instance = cls()
        return FactoryField(
            callback=lambda field, faker, k: [
                instance.build(faker=faker, **k) for i in range(faker.random_int(min=min, max=max))
            ]
        )

    def build(
        self,
        *,
        faker: Faker | None = None,
        parameters: dict[str, dict[str, Any] | FactoryCallback] | None = None,
        overwrites: dict[str, Any] | None = None,
        exclude: Container[str] = (),
        database: Database | None | Literal[False] = None,
        schema: str | None | Literal[False] = None,
    ) -> Model:
        """
        When this function is called, automacally will perform the
        generation of the model with the fake data using the
        meta.model.query(**self.fields) where the self.fields needs to be the
        data generated based on the model fields declared in the model.

        In the end it would be something like:

        >>> class UserFactory(ModelFactory):
        ...     class Meta:
        ...         model = User
        ...
        ...     name = FactoryField(parameters={"": ""})

        >>> user = UserFactory(name="XXX").build()

        The fields that are not provided will be generated using the faker library.

        If inserting values in the DB gives a SQL error (for instance for mandatory fields),
        then its ok as it is doing the right thing.
        """
        if faker is None:
            faker = self.meta.faker
        if database is None:
            database = getattr(self, "database", None)
        elif database is False:
            database = None
        if schema is None:
            schema = getattr(self, "schema", None)
        elif schema is False:
            schema = None
        if not parameters:
            parameters = {}
        if not overwrites:
            overwrites = {}
        values: dict[str, Any] = {}
        for name, field in self.meta.fields.items():
            if name in overwrites or name in exclude or name in self.__kwargs__ or field.exclude:
                continue
            current_parameters_or_callback = parameters.get(name)
            try:
                if callable(current_parameters_or_callback):
                    params = field.get_parameters(faker=faker)
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
                    values[name] = current_parameters_or_callback(
                        field,
                        faker,
                        params,
                    )
                else:
                    params = field.get_parameters(
                        faker=faker,
                        parameters=current_parameters_or_callback,
                    )
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
                    values[name] = field(faker=faker, parameters=params)
            except ExcludeValue:
                ...

        values.update(self.__kwargs__)
        values.update(overwrites)

        result = self.meta.model(**values)
        if database is not None:
            result.database = self.database
        if schema is not None:
            result.__using_schema__ = schema
        return result
