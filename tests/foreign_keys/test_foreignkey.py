import sqlite3

import asyncpg
import pymysql
import pytest
from tests.settings import DATABASE_URL

import edgy
from edgy.exceptions import FieldDefinitionError
from edgy.testclient import DatabaseTestClient as Database

pytestmark = pytest.mark.anyio

database = Database(DATABASE_URL)
models = edgy.Registry(database=database)


class Album(edgy.Model):
    id = edgy.IntegerField(primary_key=True)
    name = edgy.CharField(max_length=100)

    class Meta:
        registry = models


class Track(edgy.Model):
    id = edgy.IntegerField(primary_key=True)
    album = edgy.ForeignKey("Album", on_delete=edgy.CASCADE)
    title = edgy.CharField(max_length=100)
    position = edgy.IntegerField()

    class Meta:
        registry = models


class Organisation(edgy.Model):
    id = edgy.IntegerField(primary_key=True)
    ident = edgy.CharField(max_length=100)

    class Meta:
        registry = models


class Team(edgy.Model):
    id = edgy.IntegerField(primary_key=True)
    org = edgy.ForeignKey(Organisation, on_delete=edgy.RESTRICT)
    name = edgy.CharField(max_length=100)

    class Meta:
        registry = models


class Member(edgy.Model):
    id = edgy.IntegerField(primary_key=True)
    team = edgy.ForeignKey(Team, on_delete=edgy.SET_NULL, null=True)
    email = edgy.CharField(max_length=100)

    class Meta:
        registry = models


class Profile(edgy.Model):
    id = edgy.IntegerField(primary_key=True)
    website = edgy.CharField(max_length=100)

    class Meta:
        registry = models


class Person(edgy.Model):
    id = edgy.IntegerField(primary_key=True)
    email = edgy.CharField(max_length=100)
    profile = edgy.OneToOneField(Profile, on_delete=edgy.CASCADE)

    class Meta:
        registry = models


class AnotherPerson(edgy.Model):
    id = edgy.IntegerField(primary_key=True)
    email = edgy.CharField(max_length=100)
    profile = edgy.OneToOne(Profile, on_delete=edgy.CASCADE)

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


async def test_model_crud():
    album = await Album.query.create(name="Malibu")
    await Track.query.create(album=album, title="The Bird", position=1)
    await Track.query.create(album=album, title="Heart don't stand a chance", position=2)
    await Track.query.create(album=album, title="The Waters", position=3)

    track = await Track.query.get(title="The Bird")
    assert track.album.pk == album.pk
    await track.album.load()
    assert track.album.name == "Malibu"


async def test_select_related():
    album = await Album.query.create(name="Malibu")
    await Track.query.create(album=album, title="The Bird", position=1)
    await Track.query.create(album=album, title="Heart don't stand a chance", position=2)
    await Track.query.create(album=album, title="The Waters", position=3)

    fantasies = await Album.query.create(name="Fantasies")
    await Track.query.create(album=fantasies, title="Help I'm Alive", position=1)
    await Track.query.create(album=fantasies, title="Sick Muse", position=2)
    await Track.query.create(album=fantasies, title="Satellite Mind", position=3)

    track = await Track.query.select_related("album").get(title="The Bird")
    assert track.album.name == "Malibu"

    tracks = await Track.query.select_related("album").all()
    assert len(tracks) == 6


async def test_select_related_no_all():
    album = await Album.query.create(name="Malibu")
    await Track.query.create(album=album, title="The Bird", position=1)
    await Track.query.create(album=album, title="Heart don't stand a chance", position=2)
    await Track.query.create(album=album, title="The Waters", position=3)

    fantasies = await Album.query.create(name="Fantasies")
    await Track.query.create(album=fantasies, title="Help I'm Alive", position=1)
    await Track.query.create(album=fantasies, title="Sick Muse", position=2)
    await Track.query.create(album=fantasies, title="Satellite Mind", position=3)

    track = await Track.query.select_related("album").get(title="The Bird")
    assert track.album.name == "Malibu"

    tracks = await Track.query.select_related("album")
    assert len(tracks) == 6


async def test_fk_filter():
    malibu = await Album.query.create(name="Malibu")
    await Track.query.create(album=malibu, title="The Bird", position=1)
    await Track.query.create(album=malibu, title="Heart don't stand a chance", position=2)
    await Track.query.create(album=malibu, title="The Waters", position=3)

    fantasies = await Album.query.create(name="Fantasies")
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


async def test_multiple_fk():
    acme = await Organisation.query.create(ident="ACME Ltd")
    red_team = await Team.query.create(org=acme, name="Red Team")
    blue_team = await Team.query.create(org=acme, name="Blue Team")
    await Member.query.create(team=red_team, email="a@example.org")
    await Member.query.create(team=red_team, email="b@example.org")
    await Member.query.create(team=blue_team, email="c@example.org")
    await Member.query.create(team=blue_team, email="d@example.org")

    other = await Organisation.query.create(ident="Other ltd")
    team = await Team.query.create(org=other, name="Green Team")
    await Member.query.create(team=team, email="e@example.org")

    members = (
        await Member.query.select_related("team__org").filter(team__org__ident="ACME Ltd").all()
    )
    assert len(members) == 4
    for member in members:
        assert member.team.org.ident == "ACME Ltd"


async def test_queryset_delete_with_fk():
    malibu = await Album.query.create(name="Malibu")
    await Track.query.create(album=malibu, title="The Bird", position=1)

    wall = await Album.query.create(name="The Wall")
    await Track.query.create(album=wall, title="The Wall", position=1)

    await Track.query.filter(album=malibu).delete()
    assert await Track.query.filter(album=malibu).count() == 0
    assert await Track.query.filter(album=wall).count() == 1


async def test_queryset_update_with_fk():
    malibu = await Album.query.create(name="Malibu")
    wall = await Album.query.create(name="The Wall")
    await Track.query.create(album=malibu, title="The Bird", position=1)

    await Track.query.filter(album=malibu).update(album=wall)
    assert await Track.query.filter(album=malibu).count() == 0
    assert await Track.query.filter(album=wall).count() == 1


@pytest.mark.skipif(database.url.dialect == "sqlite", reason="Not supported on SQLite")
async def test_on_delete_cascade():
    album = await Album.query.create(name="The Wall")
    await Track.query.create(album=album, title="Hey You", position=1)
    await Track.query.create(album=album, title="Breathe", position=2)

    assert await Track.query.count() == 2

    await album.delete()

    assert await Track.query.count() == 0


@pytest.mark.skipif(database.url.dialect == "sqlite", reason="Not supported on SQLite")
async def test_on_delete_restrict():
    organisation = await Organisation.query.create(ident="Encode")
    await Team.query.create(org=organisation, name="Maintainers")

    exceptions = (
        asyncpg.exceptions.ForeignKeyViolationError,
        pymysql.err.IntegrityError,
    )

    with pytest.raises(exceptions):
        await organisation.delete()


@pytest.mark.skipif(database.url.dialect == "sqlite", reason="Not supported on SQLite")
async def test_on_delete_set_null():
    organisation = await Organisation.query.create(ident="Encode")
    team = await Team.query.create(org=organisation, name="Maintainers")
    await Member.query.create(email="member@edgy.com", team=team)

    await team.delete()

    member = await Member.query.first()
    assert member.team.pk is None


async def test_one_to_one_field_crud():
    profile = await Profile.query.create(website="https://edgy.com")
    await Person.query.create(email="info@edgy.com", profile=profile)

    person = await Person.query.get(email="info@edgy.com")
    assert person.profile.pk == profile.pk

    await person.profile.load()
    assert person.profile.website == "https://edgy.com"

    exceptions = (
        asyncpg.exceptions.UniqueViolationError,
        pymysql.err.IntegrityError,
        sqlite3.IntegrityError,
    )

    with pytest.raises(exceptions):
        await Person.query.create(email="contact@edgy.com", profile=profile)


async def test_one_to_one_crud():
    profile = await Profile.query.create(website="https://edgy.com")
    await AnotherPerson.query.create(email="info@edgy.com", profile=profile)

    person = await AnotherPerson.query.get(email="info@edgy.com")
    assert person.profile.pk == profile.pk

    await person.profile.load()
    assert person.profile.website == "https://edgy.com"

    exceptions = (
        asyncpg.exceptions.UniqueViolationError,
        pymysql.err.IntegrityError,
        sqlite3.IntegrityError,
    )

    with pytest.raises(exceptions):
        await AnotherPerson.query.create(email="contact@edgy.com", profile=profile)


async def test_nullable_foreign_key():
    await Member.query.create(email="dev@edgy.com")

    member = await Member.query.get()

    assert member.email == "dev@edgy.com"
    assert member.team.pk is None


def test_assertation_error_on_set_null():
    with pytest.raises(FieldDefinitionError) as raised:

        class MyModel(edgy.Model):
            is_active = edgy.BooleanField(default=True)

        class MyOtherModel(edgy.Model):
            model = edgy.ForeignKey(MyModel, on_delete=edgy.SET_NULL)

    assert raised.value.args[0] == "When SET_NULL is enabled, null must be True."


def test_assertation_error_on_missing_on_delete():
    with pytest.raises(FieldDefinitionError) as raised:

        class MyModel(edgy.Model):
            is_active = edgy.BooleanField(default=True)

        class MyOtherModel(edgy.Model):
            model = edgy.ForeignKey(MyModel, on_delete=None)

    assert raised.value.args[0] == "on_delete must not be null"
