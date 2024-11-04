import pytest
from pydantic import __version__

import edgy
from edgy import ModelRef
from edgy.exceptions import ModelReferenceError
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio

database = DatabaseTestClient(DATABASE_URL, full_isolation=False)
models = edgy.Registry(database=database)

pydantic_version = __version__[:3]


class TrackModelRef(ModelRef):
    __related_name__ = "tracks_set"
    title: str
    position: int


class Album(edgy.StrictModel):
    id = edgy.IntegerField(primary_key=True, autoincrement=True)
    name = edgy.CharField(max_length=100)
    tracks = edgy.RefForeignKey(TrackModelRef, null=True)

    class Meta:
        registry = models


class Track(edgy.StrictModel):
    id = edgy.IntegerField(primary_key=True, autoincrement=True)
    album = edgy.ForeignKey("Album", on_delete=edgy.CASCADE)
    title = edgy.CharField(max_length=100)
    position = edgy.IntegerField()

    class Meta:
        registry = models


class PostRef(ModelRef):
    __related_name__ = "posts_set"
    comment: str


class Post(edgy.StrictModel):
    user = edgy.ForeignKey("User")
    comment = edgy.CharField(max_length=255)

    class Meta:
        registry = models


class User(edgy.StrictModel):
    name = edgy.CharField(max_length=100, null=True)
    posts = edgy.RefForeignKey(PostRef)

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


async def test_conversion():
    user = await User.query.create(name="foo", posts=[{"comment": "dict"}])
    posts = await user.posts_set.all()
    assert posts[0].comment == "dict"


async def test_positional():
    user = await User.query.create(PostRef(comment="positional"), name="foo", posts=[])
    posts = await user.posts_set.all()
    assert posts[0].comment == "positional"


async def test_get_or_create():
    # test get or create
    user, created = await User.query.get_or_create(
        PostRef(comment="default_arg"), name="foo", posts=[]
    )
    posts = await user.posts_set.all()
    assert posts[0].comment == "default_arg"
    assert created
    user2, created = await User.query.get_or_create(
        PostRef(comment="second arg"), name="foo", posts=[]
    )
    assert not created
    assert user2 == user
    posts = await user2.posts_set.all()
    assert posts[1].comment == "second arg"

    user3, created = await User.query.update_or_create(
        PostRef(comment="third arg"), name="foo", posts=[]
    )
    posts = await user3.posts_set.all()
    assert posts[1].comment == "second arg"
    assert posts[2].comment == "third arg"


async def test_model_crud():
    track1 = TrackModelRef(title="The Bird", position=1)
    track2 = TrackModelRef(title="Heart don't stand a chance", position=2)
    track3 = TrackModelRef(title="The Waters", position=3)

    album = await Album.query.create(name="Malibu", tracks=[track1, track2, track3])

    track = await Track.query.get(title="The Bird")
    assert track.album.pk == album.pk
    await track.album.load()
    assert track.album.name == "Malibu"

    tracks = await Track.query.all()

    assert len(tracks) == 3

    albums = await Album.query.all()

    assert len(albums) == 1


async def test_select_related():
    track1 = TrackModelRef(title="The Bird", position=1)
    track2 = TrackModelRef(title="Heart don't stand a chance", position=2)
    track3 = TrackModelRef(title="The Waters", position=3)

    await Album.query.create(name="Malibu", tracks=[track1, track2, track3])

    track_f1 = TrackModelRef(title="Help I'm Alive", position=1)
    track_f2 = TrackModelRef(title="Sick Muse", position=2)
    track_f3 = TrackModelRef(title="Satellite Mind", position=3)

    await Album.query.create(name="Fantasies", tracks=[track_f1, track_f2, track_f3])

    track = await Track.query.select_related("album").get(title="The Bird")
    assert track.album.name == "Malibu"

    tracks = await Track.query.select_related("album").all()
    assert len(tracks) == 6


async def test_select_related_no_all():
    track1 = TrackModelRef(title="The Bird", position=1)
    track2 = TrackModelRef(title="Heart don't stand a chance", position=2)
    track3 = TrackModelRef(title="The Waters", position=3)

    await Album.query.create(name="Malibu", tracks=[track1, track2, track3])

    track_f1 = TrackModelRef(title="Help I'm Alive", position=1)
    track_f2 = TrackModelRef(title="Sick Muse", position=2)
    track_f3 = TrackModelRef(title="Satellite Mind", position=3)

    await Album.query.create(name="Fantasies", tracks=[track_f1, track_f2, track_f3])

    track = await Track.query.select_related("album").get(title="The Bird")
    assert track.album.name == "Malibu"

    tracks = await Track.query.select_related("album")
    assert len(tracks) == 6


async def test_fk_filter():
    track1 = TrackModelRef(title="The Bird", position=1)
    track2 = TrackModelRef(title="Heart don't stand a chance", position=2)
    track3 = TrackModelRef(title="The Waters", position=3)

    malibu = await Album.query.create(name="Malibu", tracks=[track1, track2, track3])

    track_f1 = TrackModelRef(title="Help I'm Alive", position=1)
    track_f2 = TrackModelRef(title="Sick Muse", position=2)
    track_f3 = TrackModelRef(title="Satellite Mind", position=3)

    await Album.query.create(name="Fantasies", tracks=[track_f1, track_f2, track_f3])

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
    track1 = TrackModelRef(title="The Bird", position=1)
    malibu = await Album.query.create(name="Malibu", tracks=[track1])

    track2 = TrackModelRef(title="The Wall", position=1)
    wall = await Album.query.create(name="The Wall", tracks=[track2])

    await Track.query.filter(album=malibu).delete()
    assert await Track.query.filter(album=malibu).count() == 0
    assert await Track.query.filter(album=wall).count() == 1


async def test_queryset_update_with_fk():
    track1 = TrackModelRef(title="The Bird", position=1)
    malibu = await Album.query.create(name="Malibu", tracks=[track1])
    wall = await Album.query.create(name="The Wall")

    await Track.query.filter(album=malibu).update(album=wall)
    assert await Track.query.filter(album=malibu).count() == 0
    assert await Track.query.filter(album=wall).count() == 1


@pytest.mark.skipif(database.url.dialect == "sqlite", reason="Not supported on SQLite")
async def test_on_delete_cascade():
    track1 = TrackModelRef(title="Hey You", position=1)
    track2 = TrackModelRef(title="Breathe", position=2)
    album = await Album.query.create(name="The Wall", tracks=[track1, track2])

    assert await Track.query.count() == 2

    await album.delete()

    assert await Track.query.count() == 0


@pytest.mark.parametrize(
    "to",
    [1, {"id": 2}, [3], [4, [4]], Track],
    ids=["int", "dict", "list", "list-of_lists", "model"],
)
async def test_raises_model_reference_error(to):
    with pytest.raises(ModelReferenceError):

        class User(edgy.StrictModel):
            name = edgy.CharField(max_length=100)
            users = edgy.RefForeignKey(to, null=True)

            class Meta:
                registry = models


async def test_raise_value_error_on_missing_model_fields():
    with pytest.raises(ValueError) as raised:
        await User.query.create()

    assert raised.value.errors() == [
        {
            "type": "missing",
            "loc": ("posts",),
            "msg": "Field required",
            "input": {},
            "url": f"https://errors.pydantic.dev/{pydantic_version}/v/missing",
        }
    ]


async def test_raises_model_reference_error_on_missing__related_name__():
    with pytest.raises(ModelReferenceError):

        class PostRef(ModelRef):
            comment: str

        class User(edgy.StrictModel):
            name = edgy.CharField(max_length=100)
            users = edgy.RefForeignKey(PostRef, null=True)

            class Meta:
                registry = models


async def test_on_save_select_related_no_all():
    track1 = TrackModelRef(title="The Bird", position=1)
    track2 = TrackModelRef(title="Heart don't stand a chance", position=2)
    track3 = TrackModelRef(title="The Waters", position=3)

    album = await Album.query.create(name="Malibu")
    album.tracks = [track1, track2, track3]
    await album.save()

    total = await Track.query.filter(album__id=album.pk)

    assert len(total) == 3

    track_f1 = TrackModelRef(title="Help I'm Alive", position=1)
    track_f2 = TrackModelRef(title="Sick Muse", position=2)
    track_f3 = TrackModelRef(title="Satellite Mind", position=3)

    await Album.query.create(name="Fantasies", tracks=[track_f1, track_f2, track_f3])

    track = await Track.query.select_related("album").get(title="The Bird")
    assert track.album.name == "Malibu"

    tracks = await Track.query.select_related("album")
    assert len(tracks) == 6
