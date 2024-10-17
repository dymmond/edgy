import pytest

import edgy
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio

database = DatabaseTestClient(DATABASE_URL, full_isolation=False)
models = edgy.Registry(database=database)


class Älbum(edgy.Model):
    äd = edgy.IntegerField(primary_key=True, column_name="id")
    name = edgy.CharField(max_length=100)

    class Meta:
        registry = models
        tablename = "albums"


class Track(edgy.Model):
    id = edgy.IntegerField(primary_key=True)
    album = edgy.ForeignKey("Älbum", on_delete=edgy.CASCADE, null=True, column_name="album")
    title = edgy.CharField(max_length=100)
    position = edgy.IntegerField()

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


async def test_new_create():
    track1 = await Track.query.create(title="The Bird", position=1)
    track2 = await Track.query.create(title="Heart don't stand a chance", position=2)
    await Track.query.create(title="The Waters", position=3)

    album = await Älbum.query.create(name="Malibu")
    await album.tracks_set.add(track1)
    await album.tracks_set.add(track2)
    tracks = await album.tracks_set.all()
    assert len(tracks) == 2

    await album.tracks_set.remove(track2)
    tracks = await album.tracks_set.all()
    assert len(tracks) == 1


async def test_new_create2():
    track1 = await Track.query.create(title="The Bird", position=1)
    track2 = await Track.query.create(title="Heart don't stand a chance", position=2)
    await Track.query.create(title="The Waters", position=3)

    album = await Älbum.query.create(name="Malibu", tracks_set=[track1, track2])
    tracks = await album.tracks_set.all()

    assert len(tracks) == 2


async def test_select_related():
    album = await Älbum.query.create(name="Malibu")
    await Track.query.create(album=album, title="The Bird", position=1)
    await Track.query.create(album=album, title="Heart don't stand a chance", position=2)
    await Track.query.create(album=album, title="The Waters", position=3)

    fantasies = await Älbum.query.create(name="Fantasies")
    await Track.query.create(album=fantasies, title="Help I'm Alive", position=1)
    await Track.query.create(album=fantasies, title="Sick Muse", position=2)
    await Track.query.create(album=fantasies, title="Satellite Mind", position=3)

    track = await Track.query.select_related("album").get(title="The Bird")
    assert track.album.name == "Malibu"

    tracks = await Track.query.select_related("album").all()
    assert len(tracks) == 6


async def test_select_related_no_all():
    album = await Älbum.query.create(name="Malibu")
    await Track.query.create(album=album, title="The Bird", position=1)
    await Track.query.create(album=album, title="Heart don't stand a chance", position=2)
    await Track.query.create(album=album, title="The Waters", position=3)

    fantasies = await Älbum.query.create(name="Fantasies")
    await Track.query.create(album=fantasies, title="Help I'm Alive", position=1)
    await Track.query.create(album=fantasies, title="Sick Muse", position=2)
    await Track.query.create(album=fantasies, title="Satellite Mind", position=3)

    track = await Track.query.select_related("album").get(title="The Bird")
    assert track.album.name == "Malibu"

    tracks = await Track.query.select_related("album")
    assert len(tracks) == 6


async def test_fk_filter():
    malibu = await Älbum.query.create(name="Malibu")
    await Track.query.create(album=malibu, title="The Bird", position=1)
    await Track.query.create(album=malibu, title="Heart don't stand a chance", position=2)
    await Track.query.create(album=malibu, title="The Waters", position=3)

    fantasies = await Älbum.query.create(name="Fantasies")
    await Track.query.create(album=fantasies, title="Help I'm Alive", position=1)
    await Track.query.create(album=fantasies, title="Sick Muse", position=2)
    await Track.query.create(album=fantasies, title="Satellite Mind", position=3)

    tracks = await Track.query.select_related("album").filter(album__name="Fantasies").all()
    assert len(tracks) == 3
    for track in tracks:
        assert track.album.name == "Fantasies"

    tracks = await Track.query.select_related("album").filter(album__name__icontains="fan").all()
    assert len(tracks) == 3
    for track in tracks:
        assert track.album.name == "Fantasies"

    tracks = await Track.query.filter(album__name__icontains="fan").all()
    assert len(tracks) == 3
    for track in tracks:
        assert track.album.name == "Fantasies"

    tracks = await Track.query.filter(album=malibu).select_related("album").all()
    assert len(tracks) == 3
    for track in tracks:
        assert track.album.name == "Malibu"


async def test_queryset_delete_with_fk():
    malibu = await Älbum.query.create(name="Malibu")
    await Track.query.create(album=malibu, title="The Bird", position=1)

    wall = await Älbum.query.create(name="The Wall")
    await Track.query.create(album=wall, title="The Wall", position=1)

    await Track.query.filter(album=malibu).delete()
    assert await Track.query.filter(album=malibu).count() == 0
    assert await Track.query.filter(album=wall).count() == 1


async def test_queryset_update_with_fk():
    malibu = await Älbum.query.create(name="Malibu")
    wall = await Älbum.query.create(name="The Wall")
    await Track.query.create(album=malibu, title="The Bird", position=1)

    await Track.query.filter(album=malibu).update(album=wall)
    assert await Track.query.filter(album=malibu).count() == 0
    assert await Track.query.filter(album=wall).count() == 1


@pytest.mark.skipif(database.url.dialect == "sqlite", reason="Not supported on SQLite")
async def test_on_delete_cascade():
    album = await Älbum.query.create(name="The Wall")
    await Track.query.create(album=album, title="Hey You", position=1)
    await Track.query.create(album=album, title="Breathe", position=2)

    assert await Track.query.count() == 2

    await album.delete()

    assert await Track.query.count() == 0
