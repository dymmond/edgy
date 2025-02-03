import edgy
from edgy.testing import DatabaseTestClient
from edgy.testing.factory import FactoryField, ModelFactory
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL, full_isolation=False)
models = edgy.Registry(database=database)


class ProductRef(edgy.ModelRef):
    __related_name__ = "products_set"
    id: int = -10000


class User(edgy.StrictModel):
    id: int = edgy.IntegerField(primary_key=True, autoincrement=True)
    name: str = edgy.CharField(max_length=100, null=True)
    language: str = edgy.CharField(max_length=200, null=True)
    product_ref = edgy.fields.RefForeignKey(ProductRef)

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


class Cart(edgy.StrictModel):
    products = edgy.fields.ManyToMany(Product, through_tablename=edgy.NEW_M2M_NAMING)

    class Meta:
        registry = models


def test_parametrize_factory():
    class UserFactory(ModelFactory):
        class Meta:
            model = User

        language = FactoryField(callback="language_code")
        name = FactoryField(
            callback=lambda field_instance,
            faker,
            parameters: f"{parameters['first_name']} {parameters['last_name']}",
            parameters={
                "first_name": lambda field_instance, faker, parameters: faker.name(),
                "last_name": lambda field_instance, faker, parameters: faker.name(),
            },
        )

    UserFactory().build()
    user = UserFactory().build(parameters={"name": {"first_name": "edgy", "last_name": "edgy"}})
    assert len(user.language) <= 3
    assert user.name == "edgy edgy"


def test_can_generate_and_parametrize():
    class CartFactory(ModelFactory):
        class Meta:
            model = Cart

    cart = CartFactory().build(parameters={"products": {"min": 50, "max": 50}})
    assert len(cart.products.refs) == 50
    assert not hasattr(cart.products.refs[0].product, "id")

    cart = CartFactory().build(
        parameters={"products": {"min": 10, "max": 50, "exclude_autoincrement": False}}
    )
    assert len(cart.products.refs) >= 10 and len(cart.products.refs) <= 50
    assert cart.products.refs[0].product.id is not None


def test_can_generate_and_parametrize_model_refs():
    class UserFactory(ModelFactory):
        class Meta:
            model = User

    user = UserFactory().build(parameters={"product_ref": {"min": 50, "max": 50}})
    assert len(user.product_ref) == 50
    assert user.product_ref[0].id == -10000

    user = UserFactory().build(
        parameters={
            "product_ref": {
                "min": 10,
                "max": 10,
                "exclude_autoincrement": False,
                "parameters": {"id": {"min": 199, "max": 199}},
            }
        }
    )
    assert len(user.product_ref) == 10
    assert user.product_ref[0].id == 199


def test_can_use_field_parameters():
    class CartFactory(ModelFactory):
        class Meta:
            model = Cart

        products = FactoryField(parameters={"min": 50, "max": 50})

    cart = CartFactory().build()
    assert len(cart.products.refs) == 50

    cart = CartFactory().build(parameters={"products": {"min": 10, "max": 10}})
    assert len(cart.products.refs) == 10


def test_can_use_field_callback_with_params():
    class ProductFactory(ModelFactory):
        class Meta:
            model = Product

        name = FactoryField(
            callback=lambda x, y, kwargs: f"edgy{kwargs['count']}", parameters={"count": None}
        )

    old_product = None
    for i in range(100):  # noqa
        product = ProductFactory().build(parameters={"name": {"count": i}})
        assert product.name == f"edgy{i}"
        # here the name parameter is counted up, check that the name also counts up
        assert old_product is None or product.name != old_product.name
        old_product = product


def test_can_use_field_callback_with_dynamic_params():
    class ProductFactory(ModelFactory):
        class Meta:
            model = Product

        name = FactoryField(
            callback=lambda x, y, kwargs: kwargs["name"],
            parameters={"name": lambda field, _1, _2: field.name},
        )

    product = ProductFactory().build()
    assert product.name == "name"
