import edgy
from edgy.testing import DatabaseTestClient
from edgy.testing.factory import FactoryField, ModelFactory
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL, force_rollback=True, full_isolation=True)
models = edgy.Registry(database=database)


class ProductRef(edgy.ModelRef):
    __related_name__ = "products_set"


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


def test_to_field():
    class UserFactory(ModelFactory):
        class Meta:
            model = User

        language = FactoryField(callback="language_code")
        name = FactoryField(callback="name")

    class ProductFactory(ModelFactory):
        class Meta:
            model = Product

        user = UserFactory().to_factory_field()

    product = ProductFactory().build()
    assert len(product.user.language) <= 3


def test_to_fields():
    class ProductFactory(ModelFactory):
        class Meta:
            model = Product

    class UserFactory(ModelFactory):
        class Meta:
            model = User

        language = FactoryField(callback="language_code")
        name = FactoryField(callback="name")

        products_set = ProductFactory().to_list_factory_field(min=4, max=4)

    user = UserFactory(product_ref=[]).build()
    assert len(user.products_set.refs) == 4
    assert len(user.product_ref) == 0


def test_to_fields_model_ref():
    class ProductFactory(ModelFactory):
        class Meta:
            model = Product

    class UserFactory(ModelFactory):
        class Meta:
            model = User

        language = FactoryField(callback="language_code")
        name = FactoryField(callback="name")

        product_ref = ProductFactory().to_list_factory_field(min=4, max=4)

    user = UserFactory().build()
    assert len(user.products_set.refs) == 0
    assert len(user.product_ref) == 4
