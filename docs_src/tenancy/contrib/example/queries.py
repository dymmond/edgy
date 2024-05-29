import httpx

# Query the products for the `Edgy` user from the `edgy` schema
# by passing the tenant and email header.
async with httpx.AsyncClient() as client:
    response = await client.get("/products", headers={"tenant": "edgy", "email": "edgy@esmerald.dev"})
    assert response.status_code == 200
    assert len(response.json()) == 10  # total inserted in the `edgy` schema.

# Query the shared database, so no tenant or email associated
# In the headers.
async with httpx.AsyncClient() as client:
    response = await client.get("/products")
    assert response.status_code == 200
    assert len(response.json()) == 25  # total inserted in the `shared` database.
