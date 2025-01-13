from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast, no_type_check

import monkay

from edgy import Model
from edgy.testclient.exceptions import InvalidModelError
from edgy.utils.compat import is_class_and_subclass

try:
    import faker
except ImportError:
    raise ImportError("Faker is required for the factory.") from None

if TYPE_CHECKING:
    from edgy import Database, Registry


fake: faker.Faker = faker.Faker()

EDGY_MAPPING_FAKER = {
    "IntegerField": faker.random_int(),
    "BigIntegerField": faker.random_number(),
    "BooleanField": faker.boolean(),
    "CharField": faker.name(),
    "DateField": faker.date(),
    "DateTimeField": faker.date_time(),
    "DecimalField": faker.pyfloat(),
    "DurationField": faker.time(),
    "EmailField": faker.email(),
    "FloatField": faker.pyfloat(),
    "IPAddressField": faker.ipv4(),
    "PasswordField": faker.ipv4(),
    "SmallIntegerField": faker.random_int(),
    "TextField": faker.text(),
    "TimeField": faker.time(),
    "UUIDField": faker.uuid4(),
}


class Meta:
    __slots__ = ("meta", "abstract", "database", "__edgy_fields__", "model", "registry", "schema")

    def __init__(self, meta: Any = None, **kwargs: Any) -> None:
        self.meta = meta
        self.model: bool = getattr(meta, "model", None)
        self.abstract: bool = getattr(meta, "abstract", False)
        self.registry: Registry = getattr(meta, "registry", None)
        self.database: Database = getattr(meta, "database", False)
        self.__edgy_fields__: dict[str, Any] = {}


class FactoryModelMeta(type):
    @no_type_check
    def __new__(cls, name, bases, attrs: dict[str, Any], **kwargs: Any):
        # cls: Model = super().__new__(mcls, name, bases, attrs)

        model_class = super().__new__

        parents = [parent for parent in bases if isinstance(parent, FactoryModelMeta)]
        if not parents:
            return model_class(cls, name, bases, attrs)

        meta_info_class = Meta
        model: Model = attrs.get("model") or None

        if isinstance(model, str):
            model = monkay.load(model)

        if model is None:
            raise InvalidModelError("Model is required for a factory.") from None

        # Checks if its a valid Edgy model.
        if not is_class_and_subclass(model, Model):
            raise InvalidModelError(f"Class {model.__name__} is not an Edgy model.") from None

        # Checks for the fields and meta fields.
        meta_class: object = attrs.get("Meta", type("Meta", (), {}))
        is_abstract: bool = getattr(meta_class, "abstract", False)
        registry: Registry = getattr(meta_class, "registry", model.meta.registry)
        database: Database = getattr(meta_class, "database", model.meta.registry.database)

        # Assign the meta and the fields of the meta
        meta_info = meta_info_class(
            meta=meta_class,
            is_abstract=is_abstract,
            model=model,
            registry=registry,
            database=database,
        )

        # Gets the fields
        meta_info.__edgy_fields__ = model.meta.fields
        attrs["meta"] = meta_info

        new_class = cast(type["Model"], super().__new__(cls, name, bases, attrs, **kwargs))
        breakpoint()
        return new_class


class Factory(metaclass=FactoryModelMeta):
    """
    The base that must be subclassed in case of a factory
    that must be generated for a given model.
    """

    @property
    def model_annotations(self) -> dict[str, Any]:
        return {name: field.annotation for name, field in self.meta.__edgy_fields__.items()}

    @property
    def edgy_fields(self) -> dict[str, Any]:
        return self.meta.__edgy_fields__

    @classmethod
    def build(cls) -> Model:
        """
        When this function is called, automacally will perform the
        generation of the model with the fake data using the
        meta.model.query(**self.fields) where the self.fields needs to be the
        data generated based on the model fields declared in the model.

        In the end it would be something like:

        >>> class UserFactory(Factory):
        ...     model = User

        >>> user = UserFactory(name='XXX').build()

        The fields that are not provided will be generated using the faker library.

        If inserting values in the DB gives a SQL error (for instance for mandatory fields),
        then its ok as it is doing the right thing.
        """
        raise NotImplementedError("Method build must be implemented.")
