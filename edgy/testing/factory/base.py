from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from edgy import Model

from .metaclasses import ModelFactoryMeta

if TYPE_CHECKING:
    from faker import Faker


class ModelFactory(metaclass=ModelFactoryMeta):
    """
    The base that must be subclassed in case of a factory
    that must be generated for a given model.
    """

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
        parameters: dict[str, dict[str, Any] | Callable[[ModelFactory, Faker, dict], Any]]
        | None = None,
        overwrites: dict | None = None,
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
        ...     field_parameters: dict = {}

        >>> user = UserFactory(name='XXX').build()

        The fields that are not provided will be generated using the faker library.

        If inserting values in the DB gives a SQL error (for instance for mandatory fields),
        then its ok as it is doing the right thing.
        """
        if not parameters:
            parameters = {}
        if not overwrites:
            overwrites = {}
        values = {}
        for key, field in self.edgy_fields.items():
            if field.exclude:
                continue
            field_generator: Callable[[ModelFactory, Faker, dict], Any] | None = None
            field_name = type(field).__name__
            kwargs = {}
            if key in overwrites:
                values[key] = overwrites[key]
                continue
            elif key in self.__kwargs__:
                values[key] = self.__kwargs__[key]
                continue
            if key in self.meta.default_parameters:
                if callable(self.meta.default_parameters[key]):
                    field_generator = self.meta.default_parameters[key]
                else:
                    kwargs = self.meta.default_parameters[key]
            if key in parameters:
                if callable(parameters[key]):
                    field_generator = parameters[key]
                    kwargs = {}
                else:
                    kwargs = parameters[key]
            if field_generator is None:
                values[key] = self.meta.mappings[field_name](self, self.meta.faker, kwargs)
            else:
                values[key] = field_generator(self, self.meta.faker, kwargs)

        result = self.meta.model(**values)
        if getattr(self, "database", None) is not None:
            result.database = self.database
        if getattr(self, "__using_schema__", None) is not None:
            result.__using_schema__ = self.__using_schema__
        return result
