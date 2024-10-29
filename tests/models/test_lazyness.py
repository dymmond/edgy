import edgy
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=edgy.Database(database, force_rollback=True))


class BaseUser(edgy.Model):
    id: int = edgy.IntegerField(primary_key=True, autoincrement=True)
    name: str = edgy.CharField(max_length=100, null=True)
    language: str = edgy.CharField(max_length=200, null=True)

    class Meta:
        abstract = True


class User(BaseUser):
    class Meta:
        registry = models


class Product(edgy.Model):
    id: int = edgy.IntegerField(primary_key=True, autoincrement=True)
    name: str = edgy.CharField(max_length=100, null=True)
    rating: int = edgy.IntegerField(minimum=1, maximum=5, default=1)
    in_stock: bool = edgy.BooleanField(default=False)

    class Meta:
        registry = models
        name = "products"


def test_control_lazyness():
    # test basics
    assert User.meta is models.get_model("User").meta
    # initial
    assert not BaseUser.meta._fields_are_initialized
    assert User.meta._fields_are_initialized
    assert "name" not in User.meta.columns_to_field.data
    assert Product.meta._fields_are_initialized
    assert "rating" not in Product.meta.columns_to_field.data

    # init pk stuff
    assert "id" not in Product.meta.columns_to_field.data
    assert not User.meta.fields["pk"].fieldless_pkcolumns
    assert "id" in User.meta.columns_to_field.data

    # invalidate
    models.invalidate_models()
    assert User.meta is models.get_model("User").meta
    assert not User.meta._fields_are_initialized
    assert "name" not in User.meta.columns_to_field.data
    assert not Product.meta._fields_are_initialized
    assert "rating" not in Product.meta.columns_to_field.data

    models.init_models(init_column_mappers=False, init_class_attrs=False)
    assert "name" not in User.meta.columns_to_field.data
    assert "rating" not in Product.meta.columns_to_field.data
    assert "pknames" not in Product.__dict__
    models.init_models()
    assert "name" in User.meta.columns_to_field.data
    assert "rating" in Product.meta.columns_to_field.data
