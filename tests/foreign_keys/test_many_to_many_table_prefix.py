import pytest

import edgy
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio

database = DatabaseTestClient(DATABASE_URL, full_isolation=False)
models = edgy.Registry(database=database)


class BasePrefix(edgy.StrictModel):
    name = edgy.CharField(max_length=100)

    class Meta:
        abstract = True
        registry = models
        table_prefix = "m2m"


class User(BasePrefix):
    name = edgy.CharField(max_length=100)
    albums = edgy.ManyToManyField("Album", related_name="users")

    class Meta:
        registry = models


class Album(BasePrefix):
    name = edgy.CharField(max_length=100)
    tracks = edgy.ManyToManyField("Track", related_name="albums")

    class Meta:
        registry = models


class Track(BasePrefix):
    title = edgy.CharField(max_length=100)
    position = edgy.IntegerField()

    class Meta:
        registry = models


@pytest.fixture(scope="function")
async def create_test_database():
    async with database:
        await models.create_all()
        yield
        if not database.drop:
            await models.drop_all()


async def test_add_many_to_many(create_test_database):
    albums_through_model = User.meta.fields["albums"].through

    assert albums_through_model.meta.tablename == "m2m_useralbumsthrough"

    tracks_through_model = Album.meta.fields["tracks"].through

    assert tracks_through_model.meta.tablename == "m2m_albumtracksthrough"
