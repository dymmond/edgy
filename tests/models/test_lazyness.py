import edgy
from edgy.testclient import DatabaseTestClient as Database
from tests.settings import DATABASE_URL

database = Database(url=DATABASE_URL)
models = edgy.Registry(database=database)


class BaseUser(edgy.Model):
    id: int = edgy.IntegerField(primary_key=True)
    name: str = edgy.CharField(max_length=100, null=True)
    language: str = edgy.CharField(max_length=200, null=True)

    class Meta:
        abstract = True


class User(BaseUser):
    class Meta:
        registry = models


class Product(edgy.Model):
    id: int = edgy.IntegerField(primary_key=True)
    name: str = edgy.CharField(max_length=100, null=True)
    rating: int = edgy.IntegerField(minimum=1, maximum=5, default=1)
    in_stock: bool = edgy.BooleanField(default=False)

    class Meta:
        registry = models
        name = "products"


def test_control_lazyness():
    # initial
    assert not BaseUser.meta._is_init
    assert User.meta._is_init
    assert "name" not in User.meta.columns_to_field.data
    assert Product.meta._is_init
    assert "rating" not in Product.meta.columns_to_field.data

    # init pk stuff
    assert "id" not in Product.meta.columns_to_field.data
    assert not User.meta.fields_mapping["pk"].fieldless_pkcolumns
    assert "id" in User.meta.columns_to_field.data

    # invalidate
    models.invalidate_models()
    assert not User.meta._is_init
    assert "name" not in User.meta.columns_to_field.data
    assert not Product.meta._is_init
    assert "rating" not in Product.meta.columns_to_field.data

    models.init_models(init_column_mappers=False, init_class_attrs=False)
    assert "name" not in User.meta.columns_to_field.data
    assert "rating" not in Product.meta.columns_to_field.data
    assert "pknames" not in Product.__dict__
    models.init_models()
    assert "name" in User.meta.columns_to_field.data
    assert "rating" in Product.meta.columns_to_field.data
