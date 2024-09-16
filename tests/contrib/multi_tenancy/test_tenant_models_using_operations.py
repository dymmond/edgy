from datetime import datetime

import pytest

from edgy import Database, Registry
from edgy.contrib.multi_tenancy import TenantModel
from edgy.contrib.multi_tenancy.models import TenantMixin
from edgy.core.db import fields
from edgy.exceptions import ObjectNotFound
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL, use_existing=False)
models = Registry(database=Database(database, force_rollback=True))

pytestmark = pytest.mark.anyio


def time():
    return datetime.now().time()


@pytest.fixture(autouse=True, scope="module")
async def create_test_database():
    async with database:
        await models.create_all()
        yield
        if not database.drop:
            await models.drop_all()


@pytest.fixture(autouse=True)
async def rollback_transactions():
    async with models.database:
        yield


class Tenant(TenantMixin):
    class Meta:
        registry = models


class User(TenantModel):
    id: int = fields.IntegerField(primary_key=True)
    name: str = fields.CharField(max_length=255)
    email: str = fields.EmailField(max_length=255)

    class Meta:
        registry = models
        is_tenant = True


async def test_schema_with_using():
    """
    using this:
    await User.query.using(schema='tenant_schema').filter(email="foo@bar.com").update(email="bar@foo.com")
    is causing the updating the object it without the remaining column
    using:

    user = await User.query.using(schema='tenant_schema').get(email="foo@bar.com")
    await user.update(email="bar@foo.com")
    does not updated the data
    also User.query.using(schema='tenant_schema').get(email="foo@bar.com")
    """
    tenant = await Tenant.query.create(
        schema_name="edgy", domain_url="https://edgy.dymmond.com", tenant_name="edgy"
    )

    user = await User.query.using(schema=tenant.schema_name).create(
        name="Edgy", email="edgy@edgy.dev"
    )
    total = await User.query.using(schema=tenant.schema_name).all()

    assert user.email == "edgy@edgy.dev"
    assert len(total) == 1

    await (
        User.query.using(schema=tenant.schema_name)
        .filter(email="edgy@edgy.dev")
        .update(email="bar@foo.com")
    )

    users = await User.query.using(schema=tenant.schema_name).all()
    assert len(users) == 1
    assert users[0].email == "bar@foo.com"
    assert users[0].name == "Edgy"

    user = await User.query.using(schema=tenant.schema_name).get(email="bar@foo.com")
    assert users[0].email == "bar@foo.com"
    assert users[0].name == "Edgy"

    with pytest.raises(ObjectNotFound):
        await User.query.using(schema=tenant.schema_name).get(email="edgy@edgy.dev")
