import pytest
from tests.settings import DATABASE_URL

import edgy
from edgy.exceptions import RelationshipIncompatible, RelationshipNotFound
from edgy.testclient import DatabaseTestClient as Database

pytestmark = pytest.mark.anyio

database = Database(DATABASE_URL)
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
    tracks = edgy.ManyToManyField(Track)

    class Meta:
        registry = models


class Studio(edgy.Model):
    name = edgy.CharField(max_length=255)
    users = edgy.ManyToManyField(User)
    albums = edgy.ManyToManyField(Album)

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


async def test_add_many_to_many():
    track1 = await Track.query.create(title="The Bird", position=1)
    track2 = await Track.query.create(title="Heart don't stand a chance", position=2)
    track3 = await Track.query.create(title="The Waters", position=3)

    album = await Album.query.create(name="Malibu")

    await album.tracks.add(track1)
    await album.tracks.add(track2)
    await album.tracks.add(track3)

    total_tracks = await album.tracks.all()

    assert len(total_tracks) == 3


async def test_add_many_to_many_with_repeated_field():
    track1 = await Track.query.create(title="The Bird", position=1)
    track2 = await Track.query.create(title="Heart don't stand a chance", position=2)
    track3 = await Track.query.create(title="The Waters", position=3)

    album = await Album.query.create(name="Malibu")

    await album.tracks.add(track1)
    await album.tracks.add(track1)
    await album.tracks.add(track2)
    await album.tracks.add(track3)

    total_tracks = await album.tracks.all()

    assert len(total_tracks) == 3


async def test_delete_object_reflect_on_many_to_many():
    track1 = await Track.query.create(title="The Bird", position=1)
    track2 = await Track.query.create(title="Heart don't stand a chance", position=2)
    track3 = await Track.query.create(title="The Waters", position=3)

    album = await Album.query.create(name="Malibu")

    await album.tracks.add(track1)
    await album.tracks.add(track2)
    await album.tracks.add(track3)

    total_tracks = await album.tracks.all()

    assert len(total_tracks) == 3

    await track1.delete()

    total_tracks = await album.tracks.all()

    assert len(total_tracks) == 2


async def test_delete_child_from_many_to_many():
    track1 = await Track.query.create(title="The Bird", position=1)
    track2 = await Track.query.create(title="Heart don't stand a chance", position=2)
    track3 = await Track.query.create(title="The Waters", position=3)

    album = await Album.query.create(name="Malibu")

    await album.tracks.add(track1)
    await album.tracks.add(track2)
    await album.tracks.add(track3)

    total_album_tracks = await album.tracks.all()

    assert len(total_album_tracks) == 3

    await album.tracks.remove(track1)

    total_album_tracks = await album.tracks.all()

    assert len(total_album_tracks) == 2

    total_tracks = await Track.query.all()

    assert len(total_tracks) == 3


async def test_raises_RelationshipIncompatible():
    user = await User.query.create(name="Saffier")

    album = await Album.query.create(name="Malibu")

    with pytest.raises(RelationshipIncompatible) as raised:
        await album.tracks.add(user)

    assert raised.value.args[0] == "The child is not from the type 'Track'."


async def test_raises_RelationshipNotFound():
    track1 = await Track.query.create(title="The Bird", position=1)
    track2 = await Track.query.create(title="Heart don't stand a chance", position=2)
    track3 = await Track.query.create(title="The Waters", position=3)

    album = await Album.query.create(name="Malibu")

    await album.tracks.add(track1)
    await album.tracks.add(track2)

    with pytest.raises(RelationshipNotFound) as raised:
        await album.tracks.remove(track3)

    assert (
        raised.value.args[0]
        == f"There is no relationship between 'album' and 'track: {track3.pk}'."
    )


async def test_many_to_many_many_fields():
    track1 = await Track.query.create(title="The Bird", position=1)
    track2 = await Track.query.create(title="Heart don't stand a chance", position=2)
    track3 = await Track.query.create(title="The Waters", position=3)

    album1 = await Album.query.create(name="Malibu")
    album2 = await Album.query.create(name="Santa Monica")
    album3 = await Album.query.create(name="Las Vegas")

    user1 = await User.query.create(name="Charlie")
    user2 = await User.query.create(name="Monica")
    user3 = await User.query.create(name="Snoopy")

    studio = await Studio.query.create(name="Downtown Records")

    # add tracks to albums
    await album1.tracks.add(track1)
    await album2.tracks.add(track2)
    await album3.tracks.add(track3)

    # Add users and albums to studio
    await studio.users.add(user1)
    await studio.users.add(user2)
    await studio.users.add(user3)
    await studio.albums.add(album1)
    await studio.albums.add(album2)
    await studio.albums.add(album3)

    # Start querying

    total_users = await studio.users.all()
    total_albums = await studio.albums.all()

    assert len(total_users) == 3
    assert total_users[0].pk == user1.pk
    assert total_users[1].pk == user2.pk
    assert total_users[2].pk == user3.pk

    assert len(total_albums) == 3

    total_tracks_album1 = await album1.tracks.all()
    assert len(total_tracks_album1) == 1
    assert total_tracks_album1[0].pk == track1.pk

    total_tracks_album2 = await album2.tracks.all()
    assert len(total_tracks_album2) == 1
    assert total_tracks_album2[0].pk == track2.pk

    total_tracks_album3 = await album3.tracks.all()
    assert len(total_tracks_album3) == 1
    assert total_tracks_album3[0].pk == track3.pk


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

    tracks_album = await track1.track_albumtracks_set.all()

    assert len(tracks_album) == 1
    assert tracks_album[0].pk == album.pk

    tracks_album = await track3.track_albumtracks_set.all()

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

    tracks_album = await track1.track_albumtracks_set.filter(album__name=album.name)

    assert len(tracks_album) == 1
    assert tracks_album[0].pk == album.pk

    tracks_album = await track3.track_albumtracks_set.filter(album__name=album2.name)

    assert len(tracks_album) == 1
    assert tracks_album[0].pk == album2.pk

    tracks_album = await track1.track_albumtracks_set.filter(track__title=track1.title)

    assert len(tracks_album) == 1
    assert tracks_album[0].pk == album.pk

    tracks_album = await track3.track_albumtracks_set.filter(track__title=track3.title)

    assert len(tracks_album) == 1
    assert tracks_album[0].pk == album2.pk


async def test_related_name_query_returns_nothing():
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

    tracks_album = await track1.track_albumtracks_set.filter(album__name=album2.name)

    assert len(tracks_album) == 0

    tracks_album = await track3.track_albumtracks_set.filter(album__name=album.name)

    assert len(tracks_album) == 0
