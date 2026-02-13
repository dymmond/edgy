async def create_data():
    """
    Creates mock data.
    """
    # Create some users in the main users table
    ravyn = await User.query.create(name="ravyn")

    # Create a tenant for Edgy (only)
    tenant = await Tenant.query.create(
        schema_name="edgy",
        tenant_name="edgy",
    )

    # Create a user in the `User` table inside the `edgy` tenant.
    edgy = await User.query.using(schema=tenant.schema_name).create(
        name="Edgy schema user",
    )

    # Products for Edgy (inside edgy schema)
    for i in range(10):
        await Product.query.using(schema=tenant.schema_name).create(
            name=f"Product-{i}",
            user=edgy,
        )

    # Products for Ravyn (no schema associated, defaulting to the public schema or "shared")
    for i in range(25):
        await Product.query.create(name=f"Product-{i}", user=ravyn)
