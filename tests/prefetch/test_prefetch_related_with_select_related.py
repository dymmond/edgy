import pytest

import edgy
from edgy.core.db.querysets import Prefetch
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=edgy.Database(database, force_rollback=True))


class Album(edgy.StrictModel):
    id = edgy.IntegerField(primary_key=True, autoincrement=True)
    name = edgy.CharField(max_length=100)

    class Meta:
        registry = models


class Track(edgy.StrictModel):
    id = edgy.IntegerField(primary_key=True, autoincrement=True)
    album = edgy.ForeignKey("Album", on_delete=edgy.CASCADE)
    title = edgy.CharField(max_length=100)
    position = edgy.IntegerField()

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


async def test_prefetch_related():
    album = await Album.query.create(name="Malibu")
    await Track.query.create(album=album, title="The Bird", position=1)
    await Track.query.create(album=album, title="Heart don't stand a chance", position=2)
    await Track.query.create(album=album, title="The Waters", position=3)

    fantasies = await Album.query.create(name="Fantasies")
    await Track.query.create(album=fantasies, title="Help I'm Alive", position=1)
    await Track.query.create(album=fantasies, title="Sick Muse", position=2)
    await Track.query.create(album=fantasies, title="Satellite Mind", position=3)

    track = await Track.query.prefetch_related(
        Prefetch("tracks_set", to_attr="albums", queryset=Album.query.filter())
    ).get(title="The Bird")

    assert track.album.pk == 1
    assert len(track.albums) == 1
    assert track.albums[0].name == "Malibu"


async def test_prefetch_related_with_select_related():
    album = await Album.query.create(name="Malibu")
    await Track.query.create(album=album, title="The Bird", position=1)
    await Track.query.create(album=album, title="Heart don't stand a chance", position=2)
    await Track.query.create(album=album, title="The Waters", position=3)

    fantasies = await Album.query.create(name="Fantasies")
    await Track.query.create(album=fantasies, title="Help I'm Alive", position=1)
    await Track.query.create(album=fantasies, title="Sick Muse", position=2)
    await Track.query.create(album=fantasies, title="Satellite Mind", position=3)

    track = (
        await Track.query.select_related("album")
        .prefetch_related(Prefetch("tracks_set", to_attr="albums", queryset=Album.query.filter()))
        .get(title="The Bird")
    )

    assert track.album.name == "Malibu"
    assert len(track.albums) == 1
    assert track.albums[0].name == "Malibu"


async def test_prefetch_related_with_select_related_return_multiple():
    album = await Album.query.create(name="Malibu")
    album2 = await Album.query.create(name="Malibu")
    track1 = await Track.query.create(album=album, title="The Bird", position=1)
    track2 = await Track.query.create(album=album2, title="The Bird", position=1)

    tracks = (
        await Track.query.select_related("album")
        .prefetch_related(Prefetch("tracks_set", to_attr="albums", queryset=Album.query.filter()))
        .filter(title="The Bird")
    )

    assert len(tracks) == 2
    assert tracks[0].albums[0].pk == track1.album.pk
    assert tracks[1].albums[0].pk == track2.album.pk


async def test_prefetch_related_with_select_related_return_none():
    album = await Album.query.create(name="Malibu")
    await Track.query.create(album=album, title="The Bird", position=1)

    tracks = (
        await Track.query.select_related("album")
        .prefetch_related(Prefetch("tracks_set", to_attr="albums", queryset=Album.query.filter()))
        .filter(album__id=2)
    )

    assert len(tracks) == 0
