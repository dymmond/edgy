import asyncio
import inspect
import random
import string
import time

import nest_asyncio
import pytest
import pytest_asyncio
from tests.settings import DATABASE_URL

import edgy

database = edgy.Database(DATABASE_URL)
registry = edgy.Registry(database)
pytestmark = pytest.mark.anyio
nest_asyncio.apply()


@pytest.fixture(scope="module")
def anyio_backend():
    return ("asyncio", {"debug": True})


class BaseEdgyModel(edgy.Model):
    class Meta:
        abstract = True
        registry = registry


class Product(BaseEdgyModel):
    sku: str = edgy.CharField(max_length=100, null=True)
    name: str = edgy.CharField(max_length=100)
    rating: int = edgy.IntegerField(minimum=0, maximum=5)


class ProductWithManyField(Product):
    year_created: int = edgy.IntegerField()
    year_expired: int = edgy.IntegerField(null=True)
    created_place: str = edgy.CharField(max_length=255)


class Buyer(BaseEdgyModel):
    name: str = edgy.CharField(max_length=100)
    rating: int = edgy.IntegerField(minimum=0, maximum=10)


class Item(BaseEdgyModel):
    product: Product = edgy.ForeignKey(Product, index=True)
    publisher: Buyer = edgy.ForeignKey(Buyer, index=True)
    year: int = edgy.IntegerField(nullable=True)


@pytest.fixture(autouse=True, scope="module")
async def create_test_database():
    await registry.create_all()
    yield
    await registry.drop_all()


@pytest.fixture(autouse=True)
async def rollback_transactions():
    with database.force_rollback():
        async with database:
            yield


@pytest.fixture
async def product():
    product = await Product.query.create(sku="123455", name="Soap", rating=5)
    return product


@pytest.fixture
async def buyer():
    buyer = await Buyer.query.create(name="John Doe", rating=random.randint(0, 5))
    return buyer


@pytest.fixture
async def products_in_db(num_models: int):
    products = [
        Product(
            name="".join(random.sample(string.ascii_letters, 5)),
            rating=random.randint(0, 5),
        ).model_dump()
        for i in range(0, num_models)
    ]
    await Product.query.bulk_create(products)
    return await Product.query.all()


@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.get_event_loop()
    asyncio.set_event_loop(loop)
    loop._close = loop.close
    loop.close = lambda: None
    yield loop


@pytest_asyncio.fixture
@pytest.mark.benchmark(min_rounds=1, timer=time.process_time, disable_gc=True, warmup=False)
async def async_benchmark(benchmark, event_loop):
    def _fixture_wrapper(func):
        def _func_wrapper(*args, **kwargs):
            if inspect.iscoroutinefunction(func):

                @benchmark
                def benchmarked_func():
                    a = event_loop.run_until_complete(func(*args, **kwargs))
                    return a

                return benchmarked_func
            else:
                return benchmark(func, *args, **kwargs)

        return _func_wrapper

    return _fixture_wrapper
