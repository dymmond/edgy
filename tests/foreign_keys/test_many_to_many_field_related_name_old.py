import pytest

import edgy
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=database)


class User(edgy.Model):
    name = edgy.CharField(max_length=100)

    class Meta:
        registry = models


class Track(edgy.Model):
    id = edgy.IntegerField(primary_key=True)
    title = edgy.CharField(max_length=100)
    position = edgy.IntegerField()

    class Meta:
        registry = models


class Album(edgy.Model):
    id = edgy.IntegerField(primary_key=True)
    name = edgy.CharField(max_length=100)
    tracks = edgy.ManyToManyField(Track, related_name="album_tracks")

    class Meta:
        registry = models


class Studio(edgy.Model):
    name = edgy.CharField(max_length=255)
    users = edgy.ManyToManyField(User, related_name="studio_users")
    albums = edgy.ManyToManyField(Album, related_name="studio_albums")

    class Meta:
        registry = models


@pytest.fixture(autouse=True, scope="function")
async def create_test_database():
    await models.create_all()
    yield
    await models.drop_all()


@pytest.fixture(autouse=True)
async def rollback_connections():
    with database.force_rollback():
        async with database:
            yield


async def test_related_name_query():
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

    assert album_tracks[0].pk == track1.pk
    assert album_tracks[1].pk == track2.pk

    tracks_album = await track1.album_tracks.all()

    assert len(tracks_album) == 1
    assert tracks_album[0].pk == album.pk

    tracks_album = await track3.album_tracks.all()

    assert len(tracks_album) == 1
    assert tracks_album[0].pk == album2.pk


async def test_related_name_query_nested():
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

    assert album_tracks[0].pk == track1.pk
    assert album_tracks[1].pk == track2.pk

    tracks_album = await track1.album_tracks.filter(album__name=album.name)

    assert len(tracks_album) == 1
    assert tracks_album[0].pk == album.pk

    tracks_album = await track3.album_tracks.filter(album__name=album2.name)

    assert len(tracks_album) == 1
    assert tracks_album[0].pk == album2.pk

    tracks_album = await track1.album_tracks.filter(track__title=track1.title)

    assert len(tracks_album) == 1
    assert tracks_album[0].pk == album.pk

    tracks_album = await track3.album_tracks.filter(track__title=track3.title)

    assert len(tracks_album) == 1
    assert tracks_album[0].pk == album2.pk


async def test_related_name_query_returns_nothing():
    album = await Album.query.create(name="Malibu")
    album2 = await Album.query.create(name="Santa Monica")

    track1 = await Track.query.create(title="The Bird", position=1)
    track2 = await Track.query.create(title="Heart don't stand a chance", position=2)
    track3 = await Track.query.create(title="The Waters", position=3)

    studio = await Studio.query.create(name="Saffier Records")
    studio2 = await Studio.query.create(name="Saffier Record")

    await album.tracks.add(track1)
    await album.tracks.add(track2)
    await album2.tracks.add(track3)
    await studio.albums.add(album)
    await studio.albums.add(album2)

    album_tracks = await album.tracks.all()
    assert len(album_tracks) == 2

    assert album_tracks[0].pk == track1.pk
    assert album_tracks[1].pk == track2.pk

    tracks_album = await track1.album_tracks.filter(album__name=album2.name)

    assert len(tracks_album) == 0

    tracks_album = await track3.album_tracks.filter(album__name=album.name)

    assert len(tracks_album) == 0

    studio_albums = await album.studio_albums.filter(studio=studio)

    assert len(studio_albums) == 1
    assert studio_albums[0].pk == studio.pk

    studio_albums = await album2.studio_albums.all()

    assert len(studio_albums) == 1
    assert studio_albums[0].pk == studio.pk

    studio_albums = await album2.studio_albums.filter(studio=studio2)

    assert len(studio_albums) == 0
