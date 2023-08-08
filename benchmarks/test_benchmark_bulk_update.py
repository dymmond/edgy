import random
import string
from typing import List

import pytest
from benchmarks.conftest import Product

pytestmark = pytest.mark.anyio


@pytest.mark.parametrize("num_models", [10, 20, 40, 50])
async def test_bulk_update(async_benchmark, num_models: int, products_in_db: List[Product]):
    first_name = products_in_db[0].name

    @async_benchmark
    async def update(products: List[Product]):
        await Product.query.bulk_update(products, fields=["name"])

    for product in products_in_db:
        product.name = "".join(random.sample(string.ascii_letters, 5))

    update(products_in_db)
    product = await Product.query.get(id=products_in_db[0].id)
    assert product.name != first_name
