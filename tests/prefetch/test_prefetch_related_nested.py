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
    album = edgy.ForeignKey("Album", on_delete=edgy.CASCADE, related_name="tracks")
    related_studios = edgy.ManyToMany(
        "Studio", on_delete=edgy.CASCADE, related_name="contributing_to"
    )
    title = edgy.CharField(max_length=100)
    position = edgy.IntegerField()

    class Meta:
        registry = models


class Studio(edgy.StrictModel):
    album = edgy.ForeignKey("Album", related_name="studios")
    name = edgy.CharField(max_length=255)

    class Meta:
        registry = models


class Company(edgy.StrictModel):
    studio = edgy.ForeignKey(Studio, related_name="companies")

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


async def test_prefetch_related(subtests):
    album = await Album.query.create(name="Malibu")
    track1 = await Track.query.create(album=album, title="The Bird", position=1)
    track2 = await Track.query.create(album=album, title="Heart don't stand a chance", position=2)
    await Track.query.create(album=album, title="The Waters", position=3)

    album2 = await Album.query.create(name="West")
    await Track.query.create(album=album2, title="The Bird", position=1)

    stud = await Studio.query.create(album=album, name="Valentim")

    studio = await Studio.query.prefetch_related(
        Prefetch(related_name="album__tracks", to_attr="tracks"),
    ).get(pk=stud.pk)

    assert len(studio.tracks) == 3

    stud = stud_new = await Studio.query.create(album=album2, name="New")
    await stud.contributing_to.add_many(track1, track2)

    studio = await Studio.query.prefetch_related(
        Prefetch(related_name="album__tracks", to_attr="tracks"),
    ).get(pk=stud.pk)

    assert len(studio.tracks) == 1

    with subtests.test("first empty then with results"):
        tracks = await album.tracks.order_by("-position").prefetch_related(
            Prefetch(related_name="related_studios", to_attr="album__rstudios"),
        )
        assert len(tracks) == 3
        assert tracks[0].album is not tracks[1].album
        assert tracks[1].album is not tracks[2].album
        assert tracks[0].album.rstudios == []
        assert tracks[1].album.rstudios == [stud_new]
        assert tracks[2].album.rstudios == [stud_new]

    with subtests.test("first with results then empty"):
        tracks = await album.tracks.order_by("position").prefetch_related(
            Prefetch(related_name="related_studios", to_attr="album__rstudios"),
        )
        assert len(tracks) == 3
        assert tracks[0].album is not tracks[1].album
        assert tracks[1].album is not tracks[2].album
        assert tracks[0].album.rstudios == [stud_new]
        assert tracks[1].album.rstudios == [stud_new]
        assert tracks[2].album.rstudios == []

    with subtests.test("only empty"):
        track = (
            await album.tracks.filter(position=3)
            .prefetch_related(
                Prefetch(related_name="related_studios", to_attr="album__rstudios"),
            )
            .get()
        )
        assert track.album.rstudios == []


async def test_prefetch_related_nested():
    album = await Album.query.create(name="Malibu")
    await Track.query.create(album=album, title="The Bird", position=1)

    album2 = await Album.query.create(name="West")
    await Track.query.create(album=album2, title="The Bird", position=1)

    stud = await Studio.query.create(album=album, name="Valentim")

    await Company.query.create(studio=stud)

    company = await Company.query.prefetch_related(
        Prefetch(related_name="studio__album__tracks", to_attr="tracks")
    )

    assert len(company[0].tracks) == 1

    company = await Company.query.prefetch_related(
        Prefetch(related_name="studio__album__tracks", to_attr="tracks")
    ).get(studio=stud)

    assert len(company.tracks) == 1


async def test_prefetch_related_nested_with_queryset():
    album = await Album.query.create(name="Malibu")
    await Track.query.create(album=album, title="The Bird", position=1)

    album2 = await Album.query.create(name="West")
    await Track.query.create(album=album2, title="The Bird", position=1)

    stud = await Studio.query.create(album=album, name="Valentim")

    await Company.query.create(studio=stud)

    company = await Company.query.prefetch_related(
        Prefetch(
            related_name="studio__album__tracks",
            to_attr="tracks",
            queryset=Track.query.filter(title__icontains="bird"),
        )
    )

    assert len(company[0].tracks) == 1
