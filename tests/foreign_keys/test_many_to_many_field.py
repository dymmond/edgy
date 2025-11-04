import pytest

import edgy
from edgy.exceptions import FieldDefinitionError, RelationshipIncompatible, RelationshipNotFound
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio

database = DatabaseTestClient(DATABASE_URL, full_isolation=False)
models = edgy.Registry(database=database)


class User(edgy.StrictModel):
    name = edgy.CharField(max_length=100)

    class Meta:
        registry = models


class Track(edgy.StrictModel):
    id = edgy.IntegerField(primary_key=True, autoincrement=True)
    title = edgy.CharField(max_length=100)
    position = edgy.IntegerField()

    class Meta:
        registry = models


class Album(edgy.StrictModel):
    id = edgy.IntegerField(primary_key=True, autoincrement=True)
    name = edgy.CharField(max_length=100)
    tracks = edgy.ManyToMany(Track, embed_through="embedded")

    class Meta:
        registry = models


class Studio(edgy.StrictModel):
    name = edgy.CharField(max_length=255)
    users = edgy.ManyToMany(User)
    albums = edgy.ManyToMany(Album)

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
    track1 = await Track.query.create(title="The Bird", position=1)
    track2 = await Track.query.create(title="Heart don't stand a chance", position=2)
    track3 = await Track.query.create(title="The Waters", position=3)

    album = await Album.query.create(name="Malibu")

    await album.tracks.add(track1)
    await album.tracks.add(track2)
    await album.tracks.add(track3)

    total_tracks = await album.tracks.all()

    assert len(total_tracks) == 3


async def test_create_many_to_many(create_test_database):
    album = await Album.query.create(name="Malibu")

    await album.tracks.create(title="The Bird", position=1)
    await album.tracks.create(title="Heart don't stand a chance", position=2)
    await album.tracks.create(title="The Waters", position=3)

    total_tracks = await album.tracks.all()

    assert len(total_tracks) == 3


async def test_add_many_to_many_with_repeated_field(create_test_database):
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


async def test_delete_object_reflect_on_many_to_many(create_test_database):
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


async def test_delete_child_from_many_to_many(create_test_database):
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


async def test_raises_RelationshipIncompatible(create_test_database):
    user = await User.query.create(name="Saffier")

    album = await Album.query.create(name="Malibu")

    with pytest.raises(RelationshipIncompatible) as raised:
        await album.tracks.add(user)

    assert raised.value.args[0] == "The child is not from the types 'Track', 'AlbumTracksThrough'."


async def test_raises_RelationshipNotFound(create_test_database):
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


async def test_many_to_many_many_fields(create_test_database):
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
    assert not isinstance(total_users[0], Studio.meta.fields["users"].through)
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

    # deep select_related (despite useless)
    albums = await studio.albums.select_related("tracks")
    assert albums[0]._db_loaded_or_deleted


async def test_rollback_create(create_test_database):
    studio = await Studio.query.create(name="Downtown Records")
    with pytest.raises(ValueError):
        async with studio.transaction():
            user = await studio.users.create(name="edgy")
            await studio.users.all()
            raise ValueError()
    assert user.__parent__ is User
    assert await studio.users.count() == 0


async def test_rollback_create2(create_test_database):
    studio = await Studio.query.create(name="Downtown Records")
    with pytest.raises(ValueError):
        async with Studio.transaction():
            user = await studio.users.create(name="edgy")
            await studio.users.all()
            raise ValueError()
    assert user.__parent__ is User
    assert await studio.users.count() == 0


async def test_rollback_force(create_test_database):
    studio = await Studio.query.create(name="Downtown Records")
    async with studio.transaction(force_rollback=True):
        user = await studio.users.create(name="edgy")
        await studio.users.all()
    assert user.__parent__ is User
    assert await studio.users.count() == 0


async def test_rollback_delete(create_test_database):
    studio = await Studio.query.create(name="Downtown Records")
    user = await studio.users.create(name="edgy")
    with pytest.raises(ValueError):
        async with studio.transaction():
            await studio.users.delete()
            assert await studio.users.count() == 0
            raise ValueError()
    assert user.__parent__ is User
    assert await studio.users.count() == 1


async def test_related_name_query(create_test_database):
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


async def test_related_name_query_nested(create_test_database):
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

    tracks_album = await track1.track_albumtracks_set.filter(name=album.name)

    assert len(tracks_album) == 1
    assert tracks_album[0].pk == album.pk

    tracks_album = await track3.track_albumtracks_set.filter(name=album2.name)

    assert len(tracks_album) == 1
    assert tracks_album[0].pk == album2.pk

    tracks_album = await track1.track_albumtracks_set.filter(embedded__track__title=track1.title)

    assert len(tracks_album) == 1
    assert tracks_album[0].pk == album.pk

    tracks_album = await track3.track_albumtracks_set.filter(embedded__track__title=track3.title)

    assert len(tracks_album) == 1
    assert tracks_album[0].pk == album2.pk


async def test_related_name_query_returns_nothing(create_test_database):
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

    tracks_album = await track1.track_albumtracks_set.filter(name=album2.name)

    assert len(tracks_album) == 0

    tracks_album = await track3.track_albumtracks_set.filter(name=album.name)

    assert len(tracks_album) == 0


async def test_values_list(create_test_database):
    album = await Album.query.create(
        name="Malibu",
        tracks=[
            Track(title="The Bird", position=1),
            Track(title="Heart don't stand a chance", position=2),
            Track(title="The Waters", position=3),
        ],
    )
    assert await Track.query.count() == 3
    assert await Album.query.count() == 1
    arr = await album.tracks.order_by("position").values_list("title", flat=True)
    assert arr == ["The Bird", "Heart don't stand a chance", "The Waters"]


def test_assertation_error_on_embed_through_double_underscore_attr():
    with pytest.raises(FieldDefinitionError) as raised:

        class MyModel(edgy.StrictModel):
            is_active = edgy.BooleanField(default=True)

        class MyOtherModel(edgy.StrictModel):
            model = edgy.ManyToMany(MyModel, embed_through="foo__attr")

    assert raised.value.args[0] == '"embed_through" cannot contain "__".'
