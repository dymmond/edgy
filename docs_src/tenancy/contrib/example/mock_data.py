from myapp.models import HubUser, Product, Tenant, TenantUser, User

from edgy import Database

database = Database("<YOUR-CONNECTION-STRING>")


async def create_data():
    """
    Creates mock data
    """
    # Global users
    john = await User.query.create(name="John Doe", email="john.doe@esmerald.dev")
    edgy = await User.query.create(name="Edgy", email="edgy@esmerald.dev")

    # Tenant
    edgy_tenant = await Tenant.query.create(schema_name="edgy", tenant_name="edgy")

    # HubUser - A user specific inside the edgy schema
    edgy_schema_user = await HubUser.query.using(edgy_tenant.schema_name).create(
        name="edgy", email="edgy@esmerald.dev"
    )

    await TenantUser.query.create(user=edgy, tenant=edgy_tenant)

    # Products for Edgy HubUser specific
    for i in range(10):
        await Product.query.using(edgy_tenant.schema_name).create(
            name=f"Product-{i}", user=edgy_schema_user
        )

    # Products for the John without a tenant associated
    for i in range(25):
        await Product.query.create(name=f"Product-{i}", user=john)


# Start the db
await database.connect()

# Run the create_data
await create_data()

# Close the database connection
await database.disconnect()
