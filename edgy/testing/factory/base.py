from __future__ import annotations

from collections.abc import Container
from typing import TYPE_CHECKING, Any

from edgy import Model

from .metaclasses import ModelFactoryMeta

if TYPE_CHECKING:
    from faker import Faker

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

    def build(
        self,
        *,
        faker: Faker | None = None,
        parameters: dict[str, dict[str, Any] | FactoryCallback] | None = None,
        overwrites: dict[str, Any] | None = None,
        exclude: Container[str] = (),
        save_after: bool = False,
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
        if not parameters:
            parameters = {}
        if not overwrites:
            overwrites = {}
        values = {}
        for name, field in self.meta.fields.items():
            if name in overwrites or name in exclude or name in self.__kwargs__ or field.exclude:
                continue
            current_parameters_or_callback = parameters.get(name)
            if callable(current_parameters_or_callback):
                values[name] = current_parameters_or_callback(
                    field,
                    faker,
                    field.get_parameters(faker=faker),
                )
            else:
                values[name] = field(
                    faker=faker,
                    parameters=field.get_parameters(
                        faker=faker,
                        parameters=current_parameters_or_callback,
                    ),
                )

        values.update(self.__kwargs__)
        values.update(overwrites)

        result = self.meta.model(**values)
        if getattr(self, "database", None) is not None:
            result.database = self.database
        if getattr(self, "__using_schema__", None) is not None:
            result.__using_schema__ = self.__using_schema__
        if save_after:
            return result.save()
        return result
