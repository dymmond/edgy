from typing import List

from ravyn import get
from myapp.models import Product

import edgy


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
