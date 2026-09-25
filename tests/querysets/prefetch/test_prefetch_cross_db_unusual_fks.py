import pytest

import edgy
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_ALTERNATIVE_URL, DATABASE_URL

pytestmark = pytest.mark.anyio

database = DatabaseTestClient(DATABASE_URL, drop_database=True)
database2 = DatabaseTestClient(DATABASE_ALTERNATIVE_URL, drop_database=True)
modelsa = edgy.Registry(database=database)
modelsb = edgy.Registry(database=database)
modelsc = edgy.Registry(database=database2)


class Track(edgy.Model):
    id = edgy.BigIntegerField(primary_key=True, autoincrement=True)
    album = edgy.ForeignKey(
        "Album",
        on_delete=edgy.CASCADE,
        related_name="tracks",
        related_fields=("name",),
        secret=True,
    )
    title = edgy.CharField(max_length=100)
    position = edgy.IntegerField()

    class Meta:
        registry = modelsa


class Album(edgy.Model):
    name = edgy.CharField(max_length=255, unique=True, secret=True)

    class Meta:
        registry = modelsa


class Studio(edgy.Model):
    album = edgy.ForeignKey(Album, related_name="studios", null=True, related_fields=("name",))
    primary_company = edgy.ForeignKey(
        "Company", target_registry=modelsc, related_name="+", null=True
    )
    name = edgy.CharField(max_length=255)

    class Meta:
        registry = modelsb


class Company(edgy.Model):
    studio = edgy.ForeignKey(Studio, related_name="companies", null=True, related_fields=("name",))
    name = edgy.CharField(max_length=255)

    class Meta:
        registry = modelsc


@pytest.fixture(autouse=True, scope="function")
async def create_test_database():
    async with database, database2:
        await modelsc.create_all()
        await modelsb.create_all()
        await modelsa.create_all()
        yield


@pytest.mark.parametrize("target_prefix", ["", "+", "studio__album__"])
# exclude_secrets=True validates that the force include works
@pytest.mark.parametrize("exclude_secrets", [True, False])
async def test_prefetch_crossdb_pivot(target_prefix: str, exclude_secrets: bool):
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

    company = await Company.query.get(name="Music Company")
    assert company.studio is not None
    assert company.studio.album is not None

    companies = (
        await Company.query.order_by("id")
        .exclude_secrets(exclude_secrets)
        .prefetch_related(
            edgy.Prefetch(
                to_attr=f"{target_prefix}sorted_tracks",
                queryset=Track.query.order_by("-position"),
                from_anchor="studio__album",
                related_name="tracks",
            )
        )
    )
    assert companies[0].studio is None
    assert companies[1].studio is not None
    assert companies[1].studio.album is not None
    if target_prefix:
        assert companies[1].studio.album.sorted_tracks == [track1, track2, track3]
    else:
        assert companies[1].sorted_tracks == [track1, track2, track3]


@pytest.mark.parametrize("exclude_secrets", [True, False])
async def test_prefetch_crossdb_mid(exclude_secrets):
    album = await Album.query.create(name="Malibu")
    track1 = await Track.query.create(album=album, title="The Bird", position=3)
    track2 = await Track.query.create(album=album, title="Heart don't stand a chance", position=2)
    track3 = await Track.query.create(album=album, title="The Waters", position=1)

    album2 = await Album.query.create(name="West")
    await Track.query.create(album=album2, title="The Bird", position=1)
    await Studio.query.create(album=album2, name="Not Found")
    stud = await Studio.query.create(album=album, name="Valentim")
    await Company.query.create(name="Fake company")
    comp = await Company.query.create(studio=stud, name="Music Company")
    stud.primary_company = comp
    await stud.save()

    studios = (
        await Studio.query.order_by("id")
        .exclude_secrets(exclude_secrets)
        .prefetch_related(
            edgy.Prefetch(
                to_attr="primary_company__sorted_tracks",
                queryset=Track.query.order_by("-position"),
                from_anchor="album",
                related_name="tracks",
            )
        )
    )
    assert studios[0].primary_company is None
    assert studios[1].primary_company is not None
    assert studios[1].primary_company.sorted_tracks == [track1, track2, track3]
