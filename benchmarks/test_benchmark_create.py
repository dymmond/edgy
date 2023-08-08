import random
import string

import pytest
from benchmarks.conftest import Buyer, Item, Product

pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize("num_models", [10, 20, 40])
async def test_creating_models_individually(async_benchmark, num_models: int):
    @async_benchmark
    async def create(num_models: int):
        products = []
        for _idx in range(0, num_models):
            product = await Product.query.create(
                name="".join(random.sample(string.ascii_letters, 5)),
                score=random.randint() * 100,
            )
            products.append(product)
        return products

    products = create(num_models)
    for product in products:
        assert product.id is not None


@pytest.mark.parametrize("num_models", [10, 20, 40])
async def test_creating_individually_with_related_models(
    async_benchmark, num_models: int, product: Product, buyer: Buyer
):
    @async_benchmark
    async def create_with_related_models(product: Product, buyer: Buyer, num_models: int):
        books = []
        for _idx in range(0, num_models):
            book = await Item.query.create(
                product=product,
                buyer=buyer,
                year=random.randint(0, 2000),
            )
            books.append(book)

        return books

    books = create_with_related_models(product=product, buyer=buyer, num_models=num_models)

    for book in books:
        assert book.id is not None


@pytest.mark.parametrize("num_models", [10, 20, 40])
async def test_get_or_create_when_create(async_benchmark, num_models: int):
    @async_benchmark
    async def get_or_create(num_models: int):
        products = []
        for _idx in range(0, num_models):
            product, created = await Product.query.get_or_create(
                name="".join(random.sample(string.ascii_letters, 5)),
                score=random.random() * 100,
            )
            assert created
            products.append(product)
        return products

    products = get_or_create(num_models)
    for product in products:
        assert product.id is not None


@pytest.mark.parametrize("num_models", [10, 20, 40])
async def test_update_or_create_when_create(async_benchmark, num_models: int):
    @async_benchmark
    async def update_or_create(num_models: int):
        products = []
        for _idx in range(0, num_models):
            product = await Product.query.update_or_create(
                name="".join(random.sample(string.ascii_letters, 5)),
                score=random.random() * 100,
            )
            products.append(product)
        return products

    products = update_or_create(num_models)
    for product in products:
        assert product.id is not None
