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
    await models.create_all()
    yield
    if not database.drop:
        await models.drop_all()


@pytest.fixture(autouse=True, scope="function")
async def rollback_transactions():
    with models.database.force_rollback():
        async with models:
            yield


async def test_prefetch_related():
    album = await Album.query.create(name="Malibu")
    await Track.query.create(album=album, title="The Bird", position=1)
    await Track.query.create(album=album, title="Heart don't stand a chance", position=2)
    await Track.query.create(album=album, title="The Waters", position=3)

    album2 = await Album.query.create(name="West")
    await Track.query.create(album=album2, title="The Bird", position=1)

    stud = await Studio.query.create(album=album, name="Valentim")

    studio = await Studio.query.prefetch_related(
        Prefetch(related_name="album__tracks", to_attr="tracks"),
    ).get(pk=stud.pk)

    assert len(studio.tracks) == 3

    stud = await Studio.query.create(album=album2, name="New")

    studio = await Studio.query.prefetch_related(
        Prefetch(related_name="album__tracks", to_attr="tracks"),
    ).get(pk=stud.pk)

    assert len(studio.tracks) == 1


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
