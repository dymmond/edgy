from typing import List

from ravyn import Ravyn, Gateway, get

import edgy

database = edgy.Database("<TOUR-CONNECTION-STRING>")
models = edgy.Registry(database=database)


@get("/products")
async def products() -> List[Product]:
    """
    Returns the products associated to a tenant or
    all the "shared" products if tenant is None.
    """
    products = await Product.query.all()
    return products


app = models.asgi(
    Ravyn(
        routes=[Gateway(handler=products)],
        middleware=[TenantMiddleware],
    )
)
