import pytest

import edgy
from edgy.core.db.querysets import Prefetch
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=edgy.Database(database, force_rollback=True))


class User(edgy.StrictModel):
    name = edgy.CharField(max_length=100)

    class Meta:
        registry = models


class Role(edgy.StrictModel):
    name = edgy.CharField(max_length=100)
    users = edgy.ManyToMany("User", related_name="roles")

    class Meta:
        registry = models


class SpaceGroup(edgy.StrictModel):
    role = edgy.ForeignKey(Role, related_name="groups")
    name = edgy.CharField(max_length=100)

    class Meta:
        registry = models


class Space(edgy.StrictModel):
    groups = edgy.ManyToManyField(SpaceGroup, related_name="spaces")
    name = edgy.CharField(max_length=100)

    class Meta:
        registry = models


@pytest.fixture(autouse=True, scope="module")
async def create_test_database():
    # this creates and drops the database
    async with database:
        await models.create_all()
        yield
        if not database.drop:
            await models.drop_all()


@pytest.fixture(autouse=True, scope="function")
async def rollback_transactions():
    # this rolls back
    async with models:
        yield


async def test_prefetch_m2m_directly():
    role = await Role.query.create(name="Admin")
    group1 = await SpaceGroup.query.create(name="Group 1", role=role)
    group2 = await SpaceGroup.query.create(name="Group 2", role=role)

    space = await Space.query.create(name="Space 1")
    total = await space.groups.add_many(group1, group2)

    assert len(total) == 2

    space_query = await Space.query.prefetch_related(
        Prefetch(related_name="groups", to_attr="to_groups")
    ).get(id=space.id)

    assert len(space_query.to_groups) == 2


async def test_prefetch_m2m_directly_mixed():
    role = await Role.query.create(name="Admin")
    group1 = await SpaceGroup.query.create(name="Group 1", role=role)
    group2 = await SpaceGroup.query.create(name="Group 2", role=role)

    space = await Space.query.create(name="Space 1")
    total = await space.groups.add_many(group1, group2)

    user = await User.query.create(name="Edgy")
    user2 = await User.query.create(name="Ravyn")

    await role.users.add_many(user, user2)

    assert len(total) == 2

    space_query = await Space.query.prefetch_related(
        Prefetch(
            related_name="groups__role__users",
            to_attr="to_users",
            queryset=User.query.all().distinct("id"),
        )
    ).get(id=space.id)

    assert len(space_query.to_users) == 2


async def test_prefetch_m2m_reverse_prefetch():
    role = await Role.query.create(name="Admin")
    group1 = await SpaceGroup.query.create(name="Group 1", role=role)
    group2 = await SpaceGroup.query.create(name="Group 2", role=role)

    space = await Space.query.create(name="Space 1")
    total = await space.groups.add_many(group1, group2)

    user = await User.query.create(name="Edgy")
    user2 = await User.query.create(name="Ravyn")

    await role.users.add_many(user, user2)

    assert len(total) == 2

    user_query = await User.query.prefetch_related(
        Prefetch(
            related_name="roles__groups__spaces",
            to_attr="to_spaces",
            queryset=Space.query.all().distinct("id"),
        )
    ).get(id=user.id)

    assert len(user_query.to_spaces) == 1
