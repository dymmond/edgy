import pytest
from sqlalchemy.exc import IntegrityError

import edgy
from edgy.exceptions import FieldDefinitionError
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=edgy.Database(database, force_rollback=True))


@pytest.fixture(autouse=True, scope="module")
async def create_test_database():
    async with database:
        await models.create_all()
        yield
        if not database.drop:
            await models.drop_all()


@pytest.fixture(autouse=True, scope="function")
async def rollback_connections():
    async with models:
        yield


class Album(edgy.StrictModel):
    id = edgy.IntegerField(primary_key=True, autoincrement=True)
    name = edgy.CharField(max_length=100)

    class Meta:
        registry = models


class Track(edgy.StrictModel):
    id = edgy.IntegerField(primary_key=True, autoincrement=True)
    album = edgy.ForeignKey("Album", on_delete=edgy.CASCADE, null=True)
    title = edgy.CharField(max_length=100)
    position = edgy.IntegerField()

    class Meta:
        registry = models


class Organisation(edgy.StrictModel):
    id = edgy.IntegerField(primary_key=True, autoincrement=True)
    ident = edgy.CharField(max_length=100)

    class Meta:
        registry = models


class Team(edgy.StrictModel):
    id = edgy.IntegerField(primary_key=True, autoincrement=True)
    org = edgy.ForeignKey(Organisation, on_delete=edgy.RESTRICT)
    name = edgy.CharField(max_length=100)

    class Meta:
        registry = models


class Member(edgy.StrictModel):
    id = edgy.IntegerField(primary_key=True, autoincrement=True)
    team = edgy.ForeignKey(Team, on_delete=edgy.SET_NULL, null=True)
    email = edgy.CharField(max_length=100)

    class Meta:
        registry = models


class Profile(edgy.StrictModel):
    id = edgy.IntegerField(primary_key=True, autoincrement=True)
    website = edgy.CharField(max_length=100)

    class Meta:
        registry = models


class Person(edgy.StrictModel):
    id = edgy.IntegerField(primary_key=True, autoincrement=True)
    email = edgy.CharField(max_length=100)
    profile = edgy.OneToOneField(Profile, on_delete=edgy.CASCADE, related_name=False)

    class Meta:
        registry = models


class AnotherPerson(edgy.StrictModel):
    id = edgy.IntegerField(primary_key=True, autoincrement=True)
    email = edgy.CharField(max_length=100)
    profile = edgy.OneToOne(Profile, on_delete=edgy.CASCADE)

    class Meta:
        registry = models


async def test_no_relation():
    for field in Profile.meta.fields:
        assert not field.startswith("person")


async def test_new_create():
    track1 = await Track.query.create(title="The Bird", position=1)
    track2 = await Track.query.create(title="Heart don't stand a chance", position=2)
    await Track.query.create(title="The Waters", position=3)

    album = await Album.query.create(name="Malibu")
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

    album = await Album.query.create(name="Malibu", tracks_set=[track1, track2])
    tracks = await album.tracks_set.all()

    assert len(tracks) == 2


async def test_create_via_relation_create():
    await Track.query.create(title="The Waters", position=3)

    album = await Album.query.create(name="Malibu")
    await album.tracks_set.create(title="The Bird", position=1)
    await album.tracks_set.create(title="Heart don't stand a chance", position=2)
    tracks = await album.tracks_set.all()

    assert len(tracks) == 2


async def test_create_dynamic():
    track = await Track.query.create(title="The Waters", position=3)
    track.album = Album(name="Malibu")
    await track.save()
    assert await Album.query.get(name="Malibu")
    await track.update(album=Album(name="Foo"))
    assert await Album.query.get(name="Foo")


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

    with pytest.raises(IntegrityError):
        await organisation.delete()


@pytest.mark.skipif(database.url.dialect == "sqlite", reason="Not supported on SQLite")
async def test_on_delete_set_null():
    organisation = await Organisation.query.create(ident="Encode")
    team = await Team.query.create(org=organisation, name="Maintainers")
    await Member.query.create(email="member@edgy.com", team=team)

    await team.delete()

    member = await Member.query.first()
    assert member.team is None


async def test_one_to_one_field_crud():
    profile = await Profile.query.create(website="https://edgy.com")
    await Person.query.create(email="info@edgy.com", profile=profile)

    person = await Person.query.get(email="info@edgy.com")
    assert person.profile.pk == profile.pk

    await person.profile.load()
    assert person.profile.website == "https://edgy.com"

    with pytest.raises(IntegrityError):
        await Person.query.create(email="contact@edgy.com", profile=profile)


async def test_one_to_one_crud():
    profile = await Profile.query.create(website="https://edgy.com")
    await AnotherPerson.query.create(email="info@edgy.com", profile=profile)

    person = await AnotherPerson.query.get(email="info@edgy.com")
    assert person.profile.pk == profile.pk

    await person.profile.load()
    assert person.profile.website == "https://edgy.com"

    with pytest.raises(IntegrityError):
        await AnotherPerson.query.create(email="contact@edgy.com", profile=profile)


async def test_nullable_foreign_key():
    await Member.query.create(email="dev@edgy.com")

    member = await Member.query.get()

    assert member.email == "dev@edgy.com"
    assert member.team is None


async def test_values_list(create_test_database):
    album = await Album.query.create(
        name="Malibu",
        tracks_set=[
            Track(title="The Bird", position=1),
            Track(title="Heart don't stand a chance", position=2),
            Track(title="The Waters", position=3),
        ],
    )
    assert await Track.query.count() == 3
    assert await Album.query.count() == 1
    arr = await album.tracks_set.order_by("position").values_list("title", flat=True)
    assert arr == ["The Bird", "Heart don't stand a chance", "The Waters"]


async def test_assertation_error_on_set_null():
    with pytest.raises(FieldDefinitionError) as raised:

        class MyModel(edgy.StrictModel):
            is_active = edgy.BooleanField(default=True)

        class MyOtherModel(edgy.StrictModel):
            model = edgy.ForeignKey(MyModel, on_delete=edgy.SET_NULL)

    assert raised.value.args[0] == "When SET_NULL is enabled, null must be True."


async def test_assertation_error_on_missing_on_delete():
    with pytest.raises(FieldDefinitionError) as raised:

        class MyModel(edgy.StrictModel):
            is_active = edgy.BooleanField(default=True)

        class MyOtherModel(edgy.StrictModel):
            model = edgy.ForeignKey(MyModel, on_delete=None)

    assert raised.value.args[0] == "on_delete must not be null."


async def test_assertation_error_on_embed_parent_double_underscore_attr():
    with pytest.raises(FieldDefinitionError) as raised:

        class MyModel(edgy.StrictModel):
            is_active = edgy.BooleanField(default=True)

        class MyOtherModel(edgy.StrictModel):
            model = edgy.ForeignKey(MyModel, embed_parent=("foo", "foo__attr"))

    assert (
        raised.value.args[0]
        == '"embed_parent" second argument (for embedding parent) cannot contain "__".'
    )
