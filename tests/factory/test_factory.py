import enum

import pytest
from pydantic import ValidationError

import edgy
from edgy.testing import DatabaseTestClient
from edgy.testing.exceptions import ExcludeValue
from edgy.testing.factory import FactoryField, ModelFactory
from edgy.testing.factory.metaclasses import DEFAULT_MAPPING
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL, full_isolation=False)
models = edgy.Registry(database=database)


class ProductType(enum.Enum):
    real = "real"
    virtual = "virtual"


class User(edgy.StrictModel):
    id: int = edgy.IntegerField(primary_key=True, autoincrement=True)
    name: str = edgy.CharField(max_length=100, null=True)
    language: str = edgy.CharField(max_length=200, null=True)

    class Meta:
        registry = models


class Product(edgy.StrictModel):
    id: int = edgy.IntegerField(primary_key=True, autoincrement=True)
    name: str = edgy.CharField(max_length=100, null=True)
    rating: int = edgy.IntegerField(minimum=1, maximum=5, default=1)
    in_stock: bool = edgy.BooleanField(default=False)
    user: User = edgy.fields.ForeignKey(User)
    type: ProductType = edgy.fields.ChoiceField(choices=ProductType, default=ProductType.virtual)

    class Meta:
        registry = models
        name = "products"


class Cart(edgy.StrictModel):
    products = edgy.fields.ManyToMany(Product)

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

        id = FactoryField(exclude=True)

    class ProductFactory(ModelFactory):
        class Meta:
            model = Product

        id = FactoryField(exclude=True)
        name = FactoryField()

    user = UserFactory().build()

    assert not hasattr(user, "id")
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


def test_can_use_field_callback():
    class ProductFactory(ModelFactory):
        class Meta:
            model = Product

        name = FactoryField(callback=lambda x, y, z: "edgy")

    old_product = None
    prod_factory = ProductFactory()
    for i in range(100):  # noqa
        product = prod_factory.build()
        assert product.name == "edgy"
        assert product != old_product
        old_product = product


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
        assert product != old_product
        old_product = product

    for i in range(100):  # noqa
        product = prod_factory.build(parameters={"name": {"randomly_nullify": 0}})
        assert product.name is not None
        assert product != old_product
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
        assert product is not old_product
        old_product = product

    for i in range(100):  # noqa
        product = prod_factory.build(parameters={"name": {"randomly_unset": 0}})
        assert getattr(product, "name", None) is not None
        assert product is not old_product
        old_product = product


def test_can_use_field_callback_exclude_value():
    def callback(x, y, z):
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
                ProductFactory.meta.fields["user"], ProductFactory.meta.faker, {}
            )
        elif field_type_name == "ChoiceField":
            DEFAULT_MAPPING[field_type_name](
                ProductFactory.meta.fields["type"], ProductFactory.meta.faker, {}
            )
        elif field_type_name == "RefForeignKey":
            pass
            # FIXME: provide test
        else:
            callback = DEFAULT_MAPPING[field_type_name]
            if callback:
                callback(UserFactory.meta.fields["name"], UserFactory.meta.faker, {})
