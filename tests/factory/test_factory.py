import edgy
from edgy.testing import DatabaseTestClient
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
    rating: int = edgy.IntegerField(minimum=1, maximum=5, default=1)
    in_stock: bool = edgy.BooleanField(default=False)
    user: User = edgy.fields.ForeignKey(User)

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
    assert UserFactory.meta.abstract is False
    assert UserFactory.meta.registry == models


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


def test_can_generate_and_parametrize():
    class CartFactory(ModelFactory):
        class Meta:
            model = Cart

    cart = CartFactory().build(parameters={"products": {"min": 50, "max": 50}})
    assert len(cart.products.refs) == 50

    cart = CartFactory().build(parameters={"products": {"min": 10, "max": 50}})
    assert len(cart.products.refs) >= 10 and len(cart.products.refs) <= 50


def test_can_use_field_parameters():
    class CartFactory(ModelFactory):
        class Meta:
            model = Cart

        products = FactoryField(parameters={"min": 50, "max": 50})

    cart = CartFactory().build()
    assert len(cart.products.refs) == 50

    cart = CartFactory().build(parameters={"products": {"min": 10, "max": 10}})
    assert len(cart.products.refs) == 10


def test_can_use_field_callback():
    class ProductFactory(ModelFactory):
        class Meta:
            model = Product

        name = FactoryField(callback=lambda x, y, z: "edgy")

    old_product = None
    for i in range(100):  # noqa
        product = ProductFactory().build()
        assert product.name == "edgy"
        assert product != old_product
        old_product = product
