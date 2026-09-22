import pytest

import edgy
from edgy.exceptions import QuerySetError
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL, full_isolation=False)
models = edgy.Registry(database=database)

pytestmark = pytest.mark.anyio


class User(edgy.StrictModel):
    id = edgy.IntegerField(primary_key=True, autoincrement=True)
    name = edgy.CharField(max_length=100)
    language = edgy.CharField(max_length=200, null=True)
    description = edgy.TextField(max_length=5000, null=True)

    class Meta:
        registry = models


class Profile(edgy.StrictModel):
    user = edgy.ForeignKey(User, primary_key=True)
    name = edgy.CharField(max_length=100)

    class Meta:
        registry = models


class Group(edgy.StrictModel):
    users = edgy.ManyToMany(User)
    name = edgy.CharField(max_length=100)

    class Meta:
        registry = models


@pytest.fixture(autouse=True, scope="function")
async def create_test_database():
    async with database:
        await models.create_all()
        yield
        if not database.drop:
            await models.drop_all()


async def test_raise_QuerySetError_on_only_and_defer():
    edgy.run_sync(
        User.query.create(name="John", language="PT", description="A simple description")
    )

    with pytest.raises(QuerySetError):
        edgy.run_sync(User.query.only("name").defer("language"))


@pytest.mark.parametrize(
    "query_fn,single_result",
    [
        pytest.param(lambda group: User.query.only("name", "language"), False, id="direct"),
        pytest.param(
            lambda group: Profile.query.update_embed_parent(("user", "")).only(
                "user__name", "user__language"
            ),
            True,
            id="single",
        ),
        pytest.param(lambda group: group.users.only("name", "language"), False, id="multi"),
    ],
)
async def test_only(query_fn, single_result):
    user1 = edgy.run_sync(
        User.query.create(name="John", language="PT", description="A simple description")
    )
    user2 = edgy.run_sync(
        User.query.create(name="Jane", language="EN", description="Another simple description")
    )
    edgy.run_sync(Profile.query.create(user=user1, name="A profile"))
    group = edgy.run_sync(Group.query.create(users=[user1, user2], name="A group"))
    users = edgy.run_sync(query_fn(group))

    assert len(users) == (1 if single_result else 2)
    assert users[0].model_dump() == {"id": 1, "name": "John", "language": "PT"}

    assert "description" not in users[0].model_dump()
    if not single_result:
        assert "description" not in users[1].model_dump()

    with pytest.raises(AttributeError):
        users[0].description  # noqa
    if not single_result:
        with pytest.raises(AttributeError):
            users[1].description  # noqa

    assert "description" not in users[0].model_dump()
    if not single_result:
        assert "description" not in users[1].model_dump()

    users = edgy.run_sync(query_fn(group))

    assert "description" not in users[0].model_dump()
    if not single_result:
        assert "description" not in users[1].model_dump()


async def test_only_with_all():
    edgy.run_sync(User.query.create(name="John", language="PT"))
    edgy.run_sync(
        User.query.create(name="Jane", language="EN", description="Another simple description")
    )

    users = edgy.run_sync(User.query.only("name", "language").all())

    assert len(users) == 2


async def test_only_with_filter():
    edgy.run_sync(User.query.create(name="John", language="PT"))
    edgy.run_sync(
        User.query.create(name="Jane", language="EN", description="Another simple description")
    )

    users = edgy.run_sync(User.query.filter(pk=1).only("name", "language"))

    assert len(users) == 1

    users = edgy.run_sync(User.query.filter(id=2).only("name", "language"))

    assert len(users) == 1

    users = edgy.run_sync(User.query.filter(id=2).only("name", "language").filter(id=1))

    assert len(users) == 0


async def test_only_with_exclude():
    edgy.run_sync(User.query.create(name="John", language="PT"))
    edgy.run_sync(
        User.query.create(name="Jane", language="EN", description="Another simple description")
    )

    users = edgy.run_sync(User.query.filter(pk=1).only("name", "language").exclude(id=2))

    assert len(users) == 1

    users = edgy.run_sync(User.query.filter().only("name", "language").exclude(pk=1))

    assert len(users) == 1

    users = edgy.run_sync(User.query.only("name", "language").exclude(id__in=[1, 2]))

    assert len(users) == 0


async def test_only_save():
    edgy.run_sync(User.query.create(name="John", language="PT"))

    user = edgy.run_sync(User.query.filter(pk=1).only("name", "language").get())
    user.name = "Edgy"
    user.language = "EN"
    user.description = "LOL"
    edgy.run_sync(user.save())

    user = edgy.run_sync(User.query.get(pk=1))

    assert user.name == "Edgy"
    assert user.language == "EN"


async def test_only_save_without_nullable_field():
    user = edgy.run_sync(User.query.create(name="John", language="PT", description="John"))

    assert user.description == "John"
    assert user.language == "PT"

    user = edgy.run_sync(User.query.filter(pk=1).only("description", "language").get())
    user.language = "EN"
    user.description = "A new description"
    edgy.run_sync(user.save())

    user = edgy.run_sync(User.query.get(pk=1))

    assert user.name == "John"
    assert user.language == "EN"
    assert user.description == "A new description"
