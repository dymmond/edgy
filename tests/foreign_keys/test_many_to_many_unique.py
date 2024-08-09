import pytest

import edgy
from edgy.core.db.relationships.relation import ManyRelation
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=database)


class Track(edgy.Model):
    id = edgy.IntegerField(primary_key=True)
    title = edgy.CharField(max_length=100)
    position = edgy.IntegerField()

    class Meta:
        registry = models


class Album(edgy.Model):
    id = edgy.IntegerField(primary_key=True)
    name = edgy.CharField(max_length=100)
    tracks = edgy.ManyToManyField(Track, embed_through="embedded", unique=True, index=True)

    class Meta:
        registry = models


@pytest.fixture(autouse=True, scope="module")
async def create_test_database():
    await models.create_all()
    yield
    await models.drop_all()


@pytest.fixture(autouse=True)
async def rollback_connections():
    with database.force_rollback():
        async with database:
            yield


async def test_add_many_to_many_unique_succeed():
    track1 = await Track.query.create(title="The Bird", position=1)
    track2 = await Track.query.create(title="Heart don't stand a chance", position=2)
    track3 = await Track.query.create(title="The Waters", position=3)

    album = await Album.query.create(name="Malibu", tracks=[track1, track2, track3])
    assert isinstance(track1.track_albumtrack, ManyRelation)
    retrieved_album = await track1.track_albumtrack.get()
    assert retrieved_album.pk == album.pk
    await retrieved_album.load()
    assert retrieved_album == album
    # does nothing.
    await album.tracks.add(track3)


async def test_add_many_to_many_unique_conflict():
    track1 = await Track.query.create(title="The Bird", position=1)
    track2 = await Track.query.create(title="Heart don't stand a chance", position=2)
    track3 = await Track.query.create(title="The Waters", position=3)

    album = await Album.query.create(name="Malibu", tracks=[track1, track2, track3])
    album2 = await Album.query.create(name="Karamba")
    # cannot fail because of transaction where unique problems are ignored
    assert await album2.tracks.add(track3) is None
    retrieved_album = await track3.track_albumtrack.get()
    assert retrieved_album.pk == album.pk
    await track3.track_albumtrack.remove()
    assert await album2.tracks.add(track3)
    retrieved_album = await track3.track_albumtrack.get()
    assert retrieved_album.pk == album2.pk
