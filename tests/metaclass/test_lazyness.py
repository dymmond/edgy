import edgy
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=edgy.Database(database, force_rollback=True))


class BaseUser(edgy.StrictModel):
    id: int = edgy.IntegerField(primary_key=True, autoincrement=True)
    name: str = edgy.CharField(max_length=100, null=True)
    language: str = edgy.CharField(max_length=200, null=True)

    class Meta:
        abstract = True


class User(BaseUser):
    class Meta:
        registry = models


class Product(edgy.StrictModel):
    id: int = edgy.IntegerField(primary_key=True, autoincrement=True)
    name: str = edgy.CharField(max_length=100, null=True)
    rating: int = edgy.IntegerField(gte=1, lte=5, default=1)
    in_stock: bool = edgy.BooleanField(default=False)

    class Meta:
        registry = models
        name = "products"


def test_control_lazyness():
    # test basics
    assert User.meta is models.get_model("User").meta
    # initial
    assert not BaseUser.meta._fields_are_initialized
    assert not BaseUser.meta._field_stats_are_initialized
    assert not User.meta._fields_are_initialized
    assert User.meta._field_stats_are_initialized
    assert User.meta.columns_to_field._data is None
    # lazy init
    assert User.meta._fields_are_initialized
    assert not Product.meta._fields_are_initialized
    assert Product.meta.columns_to_field._data is None
    # lazy init
    assert Product.meta._fields_are_initialized

    # init pk stuff
    assert User.meta.columns_to_field._data is None
    assert not User.meta.fields["pk"].fieldless_pkcolumns
    # thanks to fieldless_pkcolumns we are inited now
    assert "id" in User.meta.columns_to_field._data

    # invalidate
    models.invalidate_models()
    assert User.meta is models.get_model("User").meta
    # now it is uninitialized again
    assert not User.meta._fields_are_initialized
    assert User.meta.columns_to_field._data is None
    assert not Product.meta._fields_are_initialized
    assert Product.meta.columns_to_field._data is None

    models.init_models(init_column_mappers=False, init_class_attrs=False)
    # still not initialized
    assert User.meta.columns_to_field._data is None
    assert Product.meta.columns_to_field._data is None
    assert "_pkcolumns" not in Product.__dict__
    assert "_pknames" not in Product.__dict__
    models.init_models()
    assert "_pkcolumns" in Product.__dict__
    assert "_pknames" in Product.__dict__
    assert "name" in User.meta.columns_to_field._data
    assert "rating" in Product.meta.columns_to_field._data
