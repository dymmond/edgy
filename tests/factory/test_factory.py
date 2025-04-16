import enum

import pytest
from pydantic import ValidationError

import edgy
from edgy.testing import DatabaseTestClient
from edgy.testing.exceptions import ExcludeValue
from edgy.testing.factory import FactoryField, ModelFactory
from edgy.testing.factory.base import ModelFactoryContextImplementation
from edgy.testing.factory.metaclasses import DEFAULT_MAPPING
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL, full_isolation=False)
models = edgy.Registry(database=database)


class ProductType(enum.Enum):
    real = "real"
    virtual = "virtual"


class ProductRef(edgy.ModelRef):
    __related_name__ = "products_set"


class User(edgy.StrictModel):
    id: int = edgy.IntegerField(primary_key=True, autoincrement=True)
    name: str = edgy.CharField(max_length=100, null=True)
    language: str = edgy.CharField(max_length=200, null=True)
    product_ref = edgy.fields.RefForeignKey(ProductRef, null=True)

    class Meta:
        registry = models


class Product(edgy.StrictModel):
    id: int = edgy.IntegerField(primary_key=True, autoincrement=True)
    name: str = edgy.CharField(max_length=100, null=True)
    rating: int = edgy.IntegerField(gte=1, lte=5, default=1)
    in_stock: bool = edgy.BooleanField(default=False)
    user: User = edgy.fields.ForeignKey(User)
    type: ProductType = edgy.fields.ChoiceField(choices=ProductType, default=ProductType.virtual)

    class Meta:
        registry = models
        name = "products"


class Cart(edgy.StrictModel):
    products = edgy.fields.ManyToMany(Product, through_tablename=edgy.NEW_M2M_NAMING)

    class Meta:
        registry = models


def test_can_generate_factory():
    class UserFactory(ModelFactory):
        class Meta:
            model = User

    assert UserFactory.meta.model == User


def test_can_generate_factory_by_string():
    class UserFactory(ModelFactory):
        class Meta:
            model = "tests.factory.test_factory.User"

    assert UserFactory.meta.model == User


def test_can_generate_overwrite_and_exclude():
    class UserFactory(ModelFactory):
        class Meta:
            model = User

        product_ref = FactoryField(exclude=True)

    class ProductFactory(ModelFactory):
        class Meta:
            model = Product

        name = FactoryField()

    user = UserFactory().build()

    assert not hasattr(user, "product_ref")
    assert user.database == database

    product = ProductFactory().build()
    assert not hasattr(product, "id")
    assert product.user is not user
    assert product.database == database

    product = ProductFactory().build(overwrites={"user": user, "id": 999})

    assert product.id == 999
    assert product.user is user
    assert product.database == database

    # now strip User
    user = UserFactory().build(exclude={"name", "language"})
    # currently the behaviour is to set the defaults later when saving to the db
    assert getattr(user, "name", None) is None
    assert getattr(user, "language", None) is None

    # now strip Product and cause an error
    with pytest.raises(ValidationError):
        ProductFactory().build(exclude={"user"})


def test_exclude_autoincrement_factory():
    class UserFactory(ModelFactory):
        class Meta:
            model = "tests.factory.test_factory.User"

        exclude_autoincrement = False
        product_ref = FactoryField(exclude=True)

    user = UserFactory().build()

    assert hasattr(user, "id")
    assert not hasattr(user, "product_ref")


def test_sequences():
    class UserFactory(ModelFactory):
        class Meta:
            model = User

        name = FactoryField(
            callback=lambda field, context, parameters: f"name-{field.get_callcount()}"
        )
        product_ref = FactoryField(exclude=True)

    class ProductFactory(ModelFactory):
        class Meta:
            model = Product

        user = UserFactory().to_factory_field()

    user = UserFactory().build()
    assert user.name == "name-1"
    user = UserFactory().build()
    assert user.name == "name-2"

    # use the callcounts of the main factory
    product = ProductFactory().build()
    assert product.user.name == "name-1"
    product = ProductFactory().build()
    assert product.user.name == "name-2"


def test_sequences_even():
    class UserFactory(ModelFactory):
        class Meta:
            model = User

        name = FactoryField(
            callback=lambda field, context, parameters: f"name-{field.inc_callcount()}"
        )
        product_ref = FactoryField(exclude=True)

    class ProductFactory(ModelFactory):
        class Meta:
            model = Product

        user = UserFactory().to_factory_field()

    user = UserFactory().build()
    assert user.name == "name-2"
    user = UserFactory().build()
    assert user.name == "name-4"

    # use the callcounts of the main factory
    product = ProductFactory().build()
    assert product.user.name == "name-2"
    product = ProductFactory().build()
    assert product.user.name == "name-4"


def test_sequences_odd():
    class UserFactory(ModelFactory):
        class Meta:
            model = User

        name = FactoryField(
            callback=lambda field, context, parameters: f"name-{field.inc_callcount()}"
        )
        product_ref = FactoryField(exclude=True)

    class ProductFactory(ModelFactory):
        class Meta:
            model = Product

        user = UserFactory().to_factory_field()

    UserFactory.meta.fields["name"].inc_callcount(
        amount=-1, callcounts=UserFactory.meta.callcounts
    )
    UserFactory.meta.fields["name"].inc_callcount(
        amount=-1, callcounts=ProductFactory.meta.callcounts
    )
    user = UserFactory().build()
    assert user.name == "name-1"
    user = UserFactory().build()
    assert user.name == "name-3"

    # use the callcounts of the main factory
    product = ProductFactory().build()
    assert product.user.name == "name-1"
    product = ProductFactory().build()
    assert product.user.name == "name-3"


def test_exclude_autoincrement_build():
    class UserFactory(ModelFactory):
        class Meta:
            model = "tests.factory.test_factory.User"

        product_ref = FactoryField(exclude=True)

    user_factory = UserFactory()
    user = user_factory.build()

    assert not hasattr(user, "id")
    user = user_factory.build(exclude_autoincrement=False)
    assert hasattr(user, "id")


def test_can_use_field_callback():
    class ProductFactory(ModelFactory):
        class Meta:
            model = Product

        name = FactoryField(callback=lambda x, y, z: "edgy")

    prod_factory = ProductFactory()
    for i in range(100):  # noqa
        product = prod_factory.build()
        assert product.name == "edgy"


def test_nullify():
    class ProductFactory(ModelFactory):
        class Meta:
            model = Product

        name = FactoryField(callback=lambda x, y, z: "edgy", parameters={"randomly_nullify": 100})

    old_product = None
    prod_factory = ProductFactory()
    for i in range(100):  # noqa
        product = prod_factory.build()
        assert product.name is None
        # randomness can produce collisions, so use is
        assert product is not old_product
        old_product = product

    for i in range(100):  # noqa
        product = prod_factory.build(parameters={"name": {"randomly_nullify": 0}})
        assert product.name is not None
        # randomness can produce collisions, so use is
        assert product is not old_product
        old_product = product


def test_unset():
    class ProductFactory(ModelFactory):
        class Meta:
            model = Product

        name = FactoryField(callback=lambda x, y, z: "edgy", parameters={"randomly_unset": 100})

    old_product = None
    prod_factory = ProductFactory()
    for i in range(100):  # noqa
        product = prod_factory.build()
        assert getattr(product, "name", None) is None
        # randomness can produce collisions, so use is
        assert product is not old_product
        old_product = product

    for i in range(100):  # noqa
        product = prod_factory.build(parameters={"name": {"randomly_unset": 0}})
        assert getattr(product, "name", None) is not None
        # randomness can produce collisions, so use is
        assert product is not old_product
        old_product = product


def test_can_use_field_callback_exclude_value():
    def callback(field_instance, context, parameters):
        raise ExcludeValue

    class ProductFactory(ModelFactory):
        class Meta:
            model = Product

        name = FactoryField(callback=callback)

    product = ProductFactory().build(exclude=["id"])
    assert getattr(product, "name", None) is None


def test_exclude_value():
    class ProductFactory(ModelFactory):
        class Meta:
            model = Product

        name_other_name = FactoryField(exclude=True, name="name")

    product = ProductFactory().build(exclude=["id"])
    assert getattr(product, "name", None) is None


def test_mapping():
    class UserFactory(ModelFactory):
        class Meta:
            model = User

    class ProductFactory(ModelFactory):
        class Meta:
            model = Product

    for field_name in edgy.fields.__all__:
        field_type_name = getattr(edgy.fields, field_name).__name__
        if (
            "Mixin" in field_type_name
            or field_type_name == "BaseField"
            or field_type_name == "BaseFieldType"
        ):
            continue
        assert field_type_name in DEFAULT_MAPPING
        if field_type_name in {
            "ForeignKey",
            "OneToOneField",
            "OneToOne",
            "ManyToManyField",
            "ManyToMany",
        }:
            DEFAULT_MAPPING[field_type_name](
                ProductFactory.meta.fields["user"],
                ModelFactoryContextImplementation(
                    faker=ProductFactory.meta.faker,
                    exclude_autoincrement=ProductFactory.exclude_autoincrement,
                    depth=0,
                    callcounts={},
                ),
                {},
            )
        elif field_type_name == "ChoiceField" or field_type_name == "CharChoiceField":
            DEFAULT_MAPPING[field_type_name](
                ProductFactory.meta.fields["type"],
                ModelFactoryContextImplementation(
                    faker=ProductFactory.meta.faker,
                    exclude_autoincrement=ProductFactory.exclude_autoincrement,
                    depth=0,
                    callcounts={},
                ),
                {},
            )
        elif field_type_name == "RefForeignKey":
            DEFAULT_MAPPING[field_type_name](
                UserFactory.meta.fields["product_ref"],
                ModelFactoryContextImplementation(
                    faker=UserFactory.meta.faker,
                    exclude_autoincrement=UserFactory.exclude_autoincrement,
                    depth=0,
                    callcounts={},
                ),
                {},
            )
        else:
            callback = DEFAULT_MAPPING[field_type_name]
            if callback:
                callback(
                    UserFactory.meta.fields["name"],
                    ModelFactoryContextImplementation(
                        faker=UserFactory.meta.faker,
                        exclude_autoincrement=UserFactory.exclude_autoincrement,
                        depth=0,
                        callcounts={},
                    ),
                    {},
                )
