import httpx2


async def query():
    response = await httpx2.get("/products", headers={"tenant": "edgy"})

    # Total products created for `edgy` schema
    assert len(response.json()) == 10

    # Response for the "shared", no tenant associated.
    response = await httpx2.get("/products")
    assert len(response.json()) == 25
