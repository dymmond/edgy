import pytest
from pydantic import ValidationError

import edgy
from edgy.testing import DatabaseTestClient
from edgy.testing.exceptions import InvalidModelError
from edgy.testing.factory import FactoryField, ModelFactory
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL, full_isolation=False)
models = edgy.Registry(database=database)


class User(edgy.StrictModel):
    id: int = edgy.IntegerField(primary_key=True, autoincrement=True)
    name: str = edgy.CharField(max_length=100, null=True)
    language: str = edgy.CharField(max_length=200, null=True)

    class Meta:
        registry = models


class Product(edgy.StrictModel):
    id: int = edgy.IntegerField(primary_key=True, autoincrement=True)
    name: str = edgy.CharField(max_length=100, null=True)
    rating: int = edgy.IntegerField(gte=1, lte=5, default=1)
    in_stock: bool = edgy.BooleanField(default=False)
    user: User = edgy.fields.ForeignKey(User)

    class Meta:
        registry = models


class Cart(edgy.StrictModel):
    products = edgy.fields.ManyToMany(Product, through_tablename=edgy.NEW_M2M_NAMING)

    class Meta:
        registry = models


class NotAModel: ...


def test_no_model_fails():
    with pytest.raises(InvalidModelError):

        class UserFactory(ModelFactory):
            class Meta:
                pass

    with pytest.raises(InvalidModelError):

        class UserFactory2(ModelFactory):
            pass


def test_invalid_model_string_fails():
    with pytest.raises(ModuleNotFoundError):

        class UserFactory(ModelFactory):
            class Meta:
                model = "tests.foobar.skdlsdlis.dsdksdkds"


def test_invalid_model_type_string_fails():
    with pytest.raises(InvalidModelError):

        class UserFactory(ModelFactory):
            class Meta:
                model = "tests.factory.test_factory_errors.NotAModel"


def test_verify_warns_when_default_broken(capsys):
    class ProductFactory(ModelFactory):
        class Meta:
            model = Product

        name = FactoryField(callback=lambda x, y, kwargs: f"edgy{kwargs['count']}")

    captured = capsys.readouterr()
    assert (
        captured.out.strip()
        == """"ProductFactory" failed producing a valid sample model: "KeyError('count')"."""
    )


def test_verify_exception_when_default_broken_and_error_active(capsys):
    with pytest.raises(KeyError):

        class ProductFactory(ModelFactory, model_validation="error"):
            class Meta:
                model = Product

            name = FactoryField(callback=lambda x, y, kwargs: f"edgy{kwargs['count']}")


def test_verify_exception_for_validation_errors(capsys):
    with pytest.raises(ValidationError):

        class ProductFactory(ModelFactory, model_validation="pedantic"):
            class Meta:
                model = Product

            name = FactoryField(callback=lambda x, y, kwargs: 1)


def test_verify_not_warns_when_validation_failed(capsys):
    class ProductFactory(ModelFactory):
        class Meta:
            model = Product

        name = FactoryField(callback=lambda x, y, kwargs: 3)

    captured = capsys.readouterr()
    assert captured.out.strip() == ""
    # but build
    with pytest.raises(ValidationError):
        ProductFactory().build()
