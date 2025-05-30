import pytest

import edgy
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio

database = DatabaseTestClient(DATABASE_URL, full_isolation=False)
models = edgy.Registry(database=database)


class Track(edgy.StrictModel):
    id = edgy.IntegerField(primary_key=True, autoincrement=True)
    title = edgy.CharField(max_length=100)
    position = edgy.IntegerField()

    class Meta:
        registry = models


class Album(edgy.StrictModel):
    id = edgy.IntegerField(primary_key=True, autoincrement=True)
    name = edgy.CharField(max_length=100)
    tracks = edgy.ManyToMany(
        "Track", related_name=False, embed_through="", through_tablename=edgy.NEW_M2M_NAMING
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


async def test_no_relation():
    for field in Track.meta.fields:
        assert not field.endswith("_set")


async def test_no_related_name():
    album = await Album.query.create(name="Malibu")
    album2 = await Album.query.create(name="Santa Monica")

    track1 = await Track.query.create(title="The Bird", position=1)
    track2 = await Track.query.create(title="Heart don't stand a chance", position=2)
    track3 = await Track.query.create(title="The Waters", position=3)

    await album.tracks.add(track1)
    await album.tracks.add(track2)
    await album2.tracks.add(track3)

    album_tracks = await album.tracks.all()
    assert len(album_tracks) == 2
