import pytest

import edgy
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL, drop_database=True)

pytestmark = pytest.mark.anyio


@pytest.mark.parametrize("unlink_same_registry", [True, False])
async def test_copy_model_abstract(unlink_same_registry):
    models = edgy.Registry(database=database)
    models2 = edgy.Registry(database=database, schema="another")

    class Product(edgy.StrictModel):
        class Meta:
            registry = models

    class ThroughModel(edgy.StrictModel):
        class Meta:
            abstract = True

    class Cart(edgy.StrictModel):
        products = edgy.fields.ManyToMany(
            to=Product, through=ThroughModel, through_tablename=edgy.NEW_M2M_NAMING
        )

        class Meta:
            registry = models

    assert len(models.models) == 3

    assert models.get_model("Cart").meta.fields["products"].target is Product
    through = models.get_model("Cart").meta.fields["products"].through
    assert through is models.get_model(through.__name__)
    assert "ThroughModel" not in models.models

    NewCart = Cart.copy_edgy_model(registry=models2, unlink_same_registry=unlink_same_registry)
    assert "ThroughModel" not in models2.models

    # nothing changed
    assert len(models.models) == 3
    # but the copy has new models
    assert NewCart is models2.get_model("Cart")
    if not unlink_same_registry:
        # cart, through could be added because of different registry
        assert len(models2.models) == 2
        assert models2.get_model("Cart").meta.fields["products"].target is models.get_model(
            "Product"
        )
    else:
        # cart, through couldn't be added yet
        assert len(models2.models) == 1
        Product.copy_edgy_model(registry=models2)
        # cart, through could be added now
        assert len(models2.models) == 3

    through = models2.get_model("Cart").meta.fields["products"].through
    assert "_db_schemas" in through.__dict__
    assert through is models2.get_model(through.__name__)
    assert through is not models.get_model(through.__name__)
    for reg in [models, models2]:
        assert "ThroughModel" not in reg.models


@pytest.mark.parametrize("unlink_same_registry", [True, False])
async def test_copy_model_concrete_same(unlink_same_registry):
    models = edgy.Registry(database=database)
    models2 = edgy.Registry(database=database, schema="another")

    class Product(edgy.StrictModel):
        class Meta:
            registry = models

    class ThroughModel(edgy.StrictModel):
        p = edgy.fields.ForeignKey(Product)
        c = edgy.fields.ForeignKey("Cart", target_registry=models)

        class Meta:
            registry = models

    class Cart(edgy.StrictModel):
        products = edgy.fields.ManyToMany(
            to=Product, through=ThroughModel, through_tablename=edgy.NEW_M2M_NAMING
        )

        class Meta:
            registry = models

    assert len(models.models) == 3
    assert models.get_model("Cart").meta.fields["products"].target is Product
    through = models.get_model("Cart").meta.fields["products"].through
    assert through is models.get_model(through.__name__)
    # try copying

    NewCart = Cart.copy_edgy_model(registry=models2, unlink_same_registry=unlink_same_registry)

    # nothing changed
    assert len(models.models) == 3
    # but the copy has new models
    assert NewCart is models2.get_model("Cart")
    if not unlink_same_registry:
        # cart, through could be added because of different registry
        assert len(models2.models) == 2
        assert models2.get_model("Cart").meta.fields["products"].target is models.get_model(
            "Product"
        )
    else:
        # cart, through couldn't be added yet
        assert len(models2.models) == 1
        Product.copy_edgy_model(registry=models2)
        # cart, through could be added now
        assert len(models2.models) == 3

    through = models2.get_model("Cart").meta.fields["products"].through
    assert "_db_schemas" in through.__dict__
    assert through is models2.get_model(through.__name__)
    assert through is not models.get_model(through.__name__)
    assert through.__name__ == "ThroughModel"


@pytest.mark.parametrize("unlink_same_registry", [True, False])
async def test_copy_model_concrete_other(unlink_same_registry):
    models = edgy.Registry(database=database)
    models2 = edgy.Registry(database=database, schema="another")
    models3 = edgy.Registry(database=database, schema="another2")

    class Product(edgy.StrictModel):
        class Meta:
            registry = models

    class ThroughModel(edgy.StrictModel):
        p = edgy.fields.ForeignKey(Product)
        c = edgy.fields.ForeignKey("Cart", target_registry=models)

        class Meta:
            registry = models3

    class Cart(edgy.StrictModel):
        products = edgy.fields.ManyToMany(
            to=Product, through=ThroughModel, through_tablename=edgy.NEW_M2M_NAMING
        )

        class Meta:
            registry = models

    assert len(models.models) == 2
    assert len(models3.models) == 1

    assert models.get_model("Cart").meta.fields["products"].target is Product
    through = models.get_model("Cart").meta.fields["products"].through
    assert through is models3.get_model(through.__name__)

    # try copying

    NewCart = Cart.copy_edgy_model(registry=models2, unlink_same_registry=unlink_same_registry)

    # nothing changed
    assert len(models.models) == 2
    # but the copy has new models
    assert NewCart is models2.get_model("Cart")
    if not unlink_same_registry:
        # cart, through could be added because of different registry
        assert len(models2.models) == 2
        assert models2.get_model("Cart").meta.fields["products"].target is models.get_model(
            "Product"
        )
    else:
        # cart, through couldn't be added yet
        assert len(models2.models) == 1
        Product.copy_edgy_model(registry=models2)
        # cart, through could be added now
        assert len(models2.models) == 3

    through = models2.get_model("Cart").meta.fields["products"].through
    assert "_db_schemas" in through.__dict__
    assert through is models2.get_model(through.__name__)
    assert through is not models3.get_model(through.__name__)
    assert through.__name__ == "ThroughModel"
