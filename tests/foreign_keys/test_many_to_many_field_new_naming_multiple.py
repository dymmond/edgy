import pytest

import edgy
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio

database = DatabaseTestClient(DATABASE_URL, full_isolation=False)
models = edgy.Registry(database=database)


class Üser(edgy.StrictModel):
    name = edgy.CharField(max_length=100)

    class Meta:
        registry = models
        tablename = "u"


class Studio(edgy.StrictModel):
    name = edgy.CharField(max_length=255)
    users = edgy.ManyToMany(
        Üser,
        through_tablename=edgy.NEW_M2M_NAMING,
    )
    admins = edgy.ManyToMany(
        Üser,
        through_tablename=edgy.NEW_M2M_NAMING,
    )

    class Meta:
        registry = models


@pytest.fixture(autouse=True, scope="function")
async def create_test_database():
    async with database:
        await models.create_all()
        yield
        if not database.drop:
            await models.drop_all()


async def test_check_tablename():
    assert Studio.meta.fields["users"].through.meta.tablename == "studiousersthrough"
    assert Studio.meta.fields["admins"].through.meta.tablename == "studioadminsthrough"


async def test_many_to_many_many_fields():
    user1 = await Üser.query.create(name="Charlie")
    user2 = await Üser.query.create(name="Monica")
    user3 = await Üser.query.create(name="Snoopy")

    studio = await Studio.query.create(name="Downtown Records")

    # Add users and albums to studio
    await studio.users.add(user1)
    await studio.users.add(user2)
    await studio.admins.add(user2)
    await studio.users.add(user3)

    # Start querying

    total_users = await studio.users.all()

    assert len(total_users) == 3
    assert total_users[0].pk == user1.pk
    assert total_users[1].pk == user2.pk
    assert total_users[2].pk == user3.pk

    total_admins = await studio.admins.all()
    assert len(total_admins) == 1
    assert total_admins[0].pk == user2.pk
