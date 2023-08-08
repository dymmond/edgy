import random
import string

import pytest
from benchmarks.conftest import Product

pytestmark = pytest.mark.anyio


@pytest.mark.parametrize("num_models", [10, 20, 40, 50])
async def test_making_and_inserting_models_in_bulk(async_benchmark, num_models: int):
    @async_benchmark
    async def make_and_insert(num_models: int):
        products = [
            Product(
                name="".join(random.sample(string.ascii_letters, 5)),
                rating=random.randint(0, 5),
            ).model_dump()
            for i in range(0, num_models)
        ]
        assert len(products) == num_models
        await Product.query.bulk_create(products)

    make_and_insert(num_models)
