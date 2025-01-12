import pytest

import edgy
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL, drop_database=True)

pytestmark = pytest.mark.anyio


async def test_copy_registry_abstract():
    models = edgy.Registry(database=database)

    class Product(edgy.StrictModel):
        class Meta:
            registry = models

    class ThroughModel(edgy.StrictModel):
        class Meta:
            abstract = True

    class Cart(edgy.StrictModel):
        products = edgy.fields.ManyToMany(to=Product, through=ThroughModel)

        class Meta:
            registry = models

    assert len(models.models) == 3

    assert models.get_model("Cart").meta.fields["products"].target is Product
    through = models.get_model("Cart").meta.fields["products"].through
    assert through is models.get_model(through.__name__)

    # try copying
    models_copy = edgy.get_migration_prepared_registry(models.__copy__())
    assert len(models_copy.models) == 3
    assert models_copy.get_model("Cart").meta.fields["products"].target is models_copy.get_model(
        "Product"
    )
    through = models_copy.get_model("Cart").meta.fields["products"].through
    assert through is models_copy.get_model(through.__name__)


@pytest.mark.parametrize("registry_used", ["same", "other", "none", "false"])
async def test_copy_registry_concrete(registry_used):
    models = edgy.Registry(database=database)
    models2 = edgy.Registry(database=database, schema="another")

    class Product(edgy.StrictModel):
        class Meta:
            registry = models

    class ThroughModel(edgy.StrictModel):
        p = edgy.fields.ForeignKey(Product)
        c = edgy.fields.ForeignKey("Cart", target_registry=models)

        class Meta:
            if registry_used == "same":
                registry = models
            elif registry_used == "other":
                registry = models2
            elif registry_used == "none":
                registry = None
            elif registry_used == "false":
                registry = False

    class Cart(edgy.StrictModel):
        products = edgy.fields.ManyToMany(to=Product, through=ThroughModel)

        class Meta:
            registry = models

    if registry_used == "other":
        assert len(models.models) == 2
        assert len(models2.models) == 1
    else:
        assert len(models.models) == 3

    assert models.get_model("Cart").meta.fields["products"].target is Product
    if registry_used == "other":
        through = models.get_model("Cart").meta.fields["products"].through
        assert through is models2.get_model(through.__name__)
    else:
        through = models.get_model("Cart").meta.fields["products"].through
        assert through is models.get_model(through.__name__)

    # try copying
    models_copy = edgy.get_migration_prepared_registry(models.__copy__())
    # the through model is copied for having a new one. It is added to the new registry
    assert len(models_copy.models) == 3
    assert models_copy.get_model("Cart").meta.fields["products"].target is models_copy.get_model(
        "Product"
    )
    through = models_copy.get_model("Cart").meta.fields["products"].through
    assert through is models_copy.get_model(through.__name__)
