import edgy
from tests.settings import DATABASE_URL


def test_control_lazyness():
    models = edgy.Registry(database=DATABASE_URL)

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

    # test basics
    assert User.meta is models.get_model("User").meta
    # initial
    assert not BaseUser.meta._fields_are_initialized
    assert not BaseUser.meta._field_stats_are_initialized
    assert not User.meta._fields_are_initialized
    assert User.meta._field_stats_are_initialized
    assert User.meta.field_to_columns._data == {}
    assert User.meta.columns_to_field._data is None
    # lazy init
    assert User.meta._fields_are_initialized
    assert not Product.meta._fields_are_initialized
    assert Product.meta.field_to_columns._data == {}
    assert Product.meta.columns_to_field._data is None
    # lazy init
    assert Product.meta._fields_are_initialized

    # init pk stuff
    assert "id" not in User.meta.field_to_columns._data
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


def test_lazy_mappings_contains(subtests):
    models = edgy.Registry(database=DATABASE_URL)

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

    for model_class in [BaseUser, User, Product]:
        with subtests.test(model_class.__name__):
            # pk meta key
            pk_sub = 0 if model_class.meta.abstract else 1
            assert model_class.meta.columns_to_field._data is None
            assert model_class.meta.field_to_columns._data == {}
            assert model_class.meta.field_to_column_names._data == {}
            # test own contains
            assert "id" in model_class.meta.columns_to_field
            assert "notexisting" not in model_class.meta.columns_to_field
            assert (
                len(model_class.meta.columns_to_field._data)
                == len(model_class.meta.fields) - pk_sub
            )
            assert len(model_class.meta.field_to_column_names._data) == len(
                model_class.meta.fields
            )


def test_lazy_mappings_iter(subtests):
    models = edgy.Registry(database=DATABASE_URL)

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

    for model_class in [BaseUser, User, Product]:
        with subtests.test(model_class.__name__):
            # pk meta key
            pk_sub = 0 if model_class.meta.abstract else 1
            assert model_class.meta.field_to_columns._data == {}
            assert model_class.meta.field_to_column_names._data == {}
            assert model_class.meta.columns_to_field._data is None
            # now we init everything by triggering __iter__
            assert model_class.meta.field_to_columns.keys() == model_class.meta.fields.keys()
            assert (
                len(model_class.meta.columns_to_field._data)
                == len(model_class.meta.fields) - pk_sub
            )
            assert len(model_class.meta.field_to_columns._data) == len(model_class.meta.fields)
            assert len(model_class.meta.field_to_column_names._data) == len(
                model_class.meta.fields
            )


def test_lazy_mappings_length(subtests):
    models = edgy.Registry(database=DATABASE_URL)

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

    for model_class in [BaseUser, User, Product]:
        with subtests.test(model_class.__name__):
            # pk meta key
            pk_sub = 0 if model_class.meta.abstract else 1
            assert model_class.meta.field_to_columns._data == {}
            assert model_class.meta.field_to_column_names._data == {}
            assert model_class.meta.columns_to_field._data is None
            # now we init everything by triggering __len__
            assert len(model_class.meta.field_to_columns) == len(model_class.meta.fields)
            assert (
                len(model_class.meta.columns_to_field._data)
                == len(model_class.meta.fields) - pk_sub
            )
            assert len(model_class.meta.field_to_columns._data) == len(model_class.meta.fields)
            assert len(model_class.meta.field_to_column_names._data) == len(
                model_class.meta.fields
            )

            assert len(model_class.meta.columns_to_field) == len(model_class.meta.fields) - pk_sub
            assert len(model_class.meta.field_to_columns) == len(model_class.meta.fields)
            assert len(model_class.meta.field_to_column_names) == len(model_class.meta.fields)
