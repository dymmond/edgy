from typing import List

from esmerald import Esmerald, Gateway, get
from myapp.middleware import TenantMiddleware
from myapp.models import Product

import edgy

database = edgy.Database("<TOUR-CONNECTION-STRING>")
models = edgy.Registry(database=database)


@get("/products")
async def products() -> List[Product]:
    """
    Returns the products associated to a tenant or
    all the "shared" products if tenant is None.

    The tenant was set in the `TenantMiddleware` which
    means that there is no need to use the `using` anymore.
    """
    products = await Product.query.all()
    return products


app = models.asgi(
    Esmerald(
        routes=[Gateway(handler=products)],
        middleware=[TenantMiddleware],
    )
)
