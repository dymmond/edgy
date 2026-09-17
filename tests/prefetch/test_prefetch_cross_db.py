import pytest

import edgy
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_ALTERNATIVE_URL, DATABASE_URL

pytestmark = pytest.mark.anyio

database = DatabaseTestClient(DATABASE_URL, full_isolation=False)
database2 = DatabaseTestClient(DATABASE_ALTERNATIVE_URL, full_isolation=False)
modelsa = edgy.Registry(database=database)
modelsb = edgy.Registry(database=database)
modelsc = edgy.Registry(database=database2)


class Track(edgy.Model):
    id = edgy.BigIntegerField(primary_key=True, autoincrement=True)
    album = edgy.ForeignKey("Album", on_delete=edgy.CASCADE, related_name="tracks")
    title = edgy.CharField(max_length=100)
    position = edgy.IntegerField()

    class Meta:
        registry = modelsa


class Album(edgy.Model):
    name = edgy.CharField(max_length=255)

    class Meta:
        registry = modelsa


class Studio(edgy.Model):
    album = edgy.ForeignKey("Album", related_name="studios")
    name = edgy.CharField(max_length=255)

    class Meta:
        registry = modelsb


class Company(edgy.Model):
    studio = edgy.ForeignKey(Studio, related_name="companies", null=True)
    name = edgy.CharField(max_length=255)

    class Meta:
        registry = modelsc


@pytest.fixture(autouse=True, scope="function")
async def create_test_database():
    async with database, database2:
        await modelsb.create_all()
        await modelsa.create_all()
        yield
        if not database.drop:
            await modelsa.drop_all()
            await modelsc.drop_all()

        if not database.drop:
            await modelsb.drop_all()


@pytest.mark.parametrize("target_prefix", ["", "+", "studio__album__"])
async def test_prefetch_crossdb_pivot(target_prefix: str):
    album = await Album.query.create(name="Malibu")
    track1 = await Track.query.create(album=album, title="The Bird", position=3)
    track2 = await Track.query.create(album=album, title="Heart don't stand a chance", position=2)
    track3 = await Track.query.create(album=album, title="The Waters", position=1)

    album2 = await Album.query.create(name="West")
    await Track.query.create(album=album2, title="The Bird", position=1)
    await Studio.query.create(album=album2, name="Not Found")
    stud = await Studio.query.create(album=album, name="Valentim")
    await Company.query.create(name="Fake company")
    await Company.query.create(studio=stud, name="Music Company")

    companies = await Company.query.prefetch_related(
        edgy.Prefetch(
            to_attr=f"{target_prefix}sorted_tracks",
            queryset=Track.query.order_by("-position"),
            from_anchor="studio__album",
            related_name="tracks",
        )
    )
    assert companies[0].studio is None
    assert companies[1].studio is not None
    if target_prefix:
        assert companies[1].studio.album.sorted_tracks == [track1, track2, track3]
    else:
        assert companies[1].sorted_tracks == [track1, track2, track3]
