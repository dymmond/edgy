import pytest

import edgy
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=database)


class Album(edgy.Model):
    id = edgy.IntegerField(primary_key=True)
    name = edgy.CharField(max_length=100)

    class Meta:
        registry = models


class Track(edgy.Model):
    id = edgy.IntegerField(primary_key=True)
    album = edgy.ForeignKey("Album", on_delete=edgy.CASCADE, related_name="tracks")
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
    team = edgy.ForeignKey(Team, on_delete=edgy.SET_NULL, null=True, related_name="members")
    second_team = edgy.ForeignKey(
        Team, on_delete=edgy.SET_NULL, null=True, related_name="team_members"
    )
    email = edgy.CharField(max_length=100)
    name = edgy.CharField(max_length=255, null=True)

    class Meta:
        registry = models


class User(edgy.Model):
    id = edgy.IntegerField(primary_key=True)
    name = edgy.CharField(max_length=255, null=True)
    member = edgy.ForeignKey(Member, on_delete=edgy.SET_NULL, null=True, related_name="users")

    class Meta:
        registry = models


class Profile(edgy.Model):
    user = edgy.ForeignKey(User, on_delete=edgy.CASCADE, null=False, related_name="profiles")
    profile_type = edgy.CharField(max_length=255, null=False)

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


async def test_related_field():
    album = await Album.query.create(name="Malibu")
    album2 = await Album.query.create(name="Queen")

    track1 = await Track.query.create(album=album, title="The Bird", position=1)
    track2 = await Track.query.create(album=album, title="Heart don't stand a chance", position=2)
    track3 = await Track.query.create(album=album2, title="The Waters", position=3)

    tracks_album_one = await album.tracks.all()
    tracks_and_titles = [track.title for track in tracks_album_one]

    assert len(tracks_album_one) == 2
    assert track1.title in tracks_and_titles
    assert track2.title in tracks_and_titles
    assert track3.title not in tracks_and_titles

    tracks_album_two = await album2.tracks.all()
    tracks_and_titles = [track.title for track in tracks_album_two]

    assert len(tracks_album_two) == 1
    assert track3.title in tracks_and_titles


async def test_related_field_with_filter():
    album = await Album.query.create(name="Malibu")
    album2 = await Album.query.create(name="Queen")

    track = await Track.query.create(album=album, title="The Bird", position=1)
    await Track.query.create(album=album, title="Heart don't stand a chance", position=2)
    await Track.query.create(album=album2, title="The Waters", position=3)

    tracks_album_one = await album.tracks.filter(title=track.title)

    assert len(tracks_album_one) == 1
    assert tracks_album_one[0].pk == track.pk


async def test_related_field_with_filter_return_empty():
    album = await Album.query.create(name="Malibu")
    album2 = await Album.query.create(name="Queen")

    await Track.query.create(album=album, title="The Bird", position=1)
    await Track.query.create(album=album, title="Heart don't stand a chance", position=2)
    track = await Track.query.create(album=album2, title="The Waters", position=3)

    tracks_album_one = await album.tracks.filter(title=track.title)

    assert len(tracks_album_one) == 0


async def test_related_name_empty():
    acme = await Organisation.query.create(ident="ACME Ltd")
    await Team.query.create(org=acme, name="Red Team")
    await Team.query.create(org=acme, name="Blue Team")

    teams = await acme.teams_set.all()

    assert len(teams) == 2


async def test_related_name_empty_return_one_result():
    acme = await Organisation.query.create(ident="ACME Ltd")
    red_team = await Team.query.create(org=acme, name="Red Team")
    await Team.query.create(org=acme, name="Blue Team")

    teams = await acme.teams_set.filter(name=red_team.name)

    assert len(teams) == 1
    assert teams[0].pk == red_team.pk


async def test_related_name_empty_return_one_result_with_limit():
    acme = await Organisation.query.create(ident="ACME Ltd")
    red_team = await Team.query.create(org=acme, name="Red Team")
    await Team.query.create(org=acme, name="Blue Team")

    teams = await acme.teams_set.filter(name=red_team.name).limit(1)

    assert len(teams) == 1
    assert teams[0].pk == red_team.pk


async def test_related_name_empty_return_one_result_with_limits():
    acme = await Organisation.query.create(ident="ACME Ltd")
    await Team.query.create(org=acme, name="Red Team")
    await Team.query.create(org=acme, name="Blue Team")

    teams = await acme.teams_set.filter().limit(1)

    assert len(teams) == 1

    teams = await acme.teams_set.filter().limit(2)

    assert len(teams) == 2


async def test_related_name_nested_query():
    acme = await Organisation.query.create(ident="ACME Ltd")
    red_team = await Team.query.create(org=acme, name="Red Team")
    blue_team = await Team.query.create(org=acme, name="Blue Team")

    # members
    charlie = await Member.query.create(team=red_team, email="charlie@redteam.com")
    brown = await Member.query.create(team=red_team, email="brown@redteam.com")
    monica = await Member.query.create(team=blue_team, email="monica@blueteam.com")
    snoopy = await Member.query.create(team=blue_team, email="snoopy@blueteam.com")

    teams = await acme.teams_set.all()

    assert len(teams) == 2

    # red team
    teams = await acme.teams_set.filter(members=red_team)

    assert len(teams) == 1
    assert teams[0].pk == red_team.pk

    # blue team
    teams = await acme.teams_set.filter(members=blue_team).get()

    assert teams.pk == blue_team.pk

    # nested_field by team
    teams = await acme.teams_set.filter(members__email__iexact=charlie.email)

    assert len(teams) == 1
    assert teams[0].pk == red_team.pk

    teams = await acme.teams_set.filter(members__email=brown.email)

    assert len(teams) == 1
    assert teams[0].pk == red_team.pk

    teams = await acme.teams_set.filter(members__email=monica.email)

    assert len(teams) == 1
    assert teams[0].pk == blue_team.pk

    teams = await acme.teams_set.filter(members__email=snoopy.email)

    assert len(teams) == 1
    assert teams[0].pk == blue_team.pk


@pytest.mark.skipif(database.url.dialect == "mysql", reason="Not supported on MySQL")
@pytest.mark.skipif(database.url.dialect == "sqlite", reason="Not supported on SQLite")
async def test_related_name_nested_query_multiple_foreign_keys_and_nested():
    acme = await Organisation.query.create(ident="ACME Ltd")
    red_team = await Team.query.create(org=acme, name="Red Team")
    blue_team = await Team.query.create(org=acme, name="Blue Team")
    green_team = await Team.query.create(org=acme, name="Green Team")

    # members
    charlie = await Member.query.create(
        team=red_team, email="charlie@redteam.com", second_team=green_team, name="Charlie"
    )
    brown = await Member.query.create(team=red_team, email="brown@redteam.com", name="Brown")
    monica = await Member.query.create(
        team=blue_team, email="monica@blueteam.com", second_team=green_team, name="Monica"
    )
    snoopy = await Member.query.create(team=blue_team, email="snoopy@blueteam.com", name="Snoopy")

    teams = await acme.teams_set.all()

    assert len(teams) == 3

    # red team
    teams = await acme.teams_set.filter(members=red_team)

    assert len(teams) == 1
    assert teams[0].pk == red_team.pk

    # blue team
    teams = await acme.teams_set.filter(members=blue_team)

    assert len(teams) == 1
    assert teams[0].pk == blue_team.pk

    # blue team
    teams = await acme.teams_set.filter(members=green_team)

    assert len(teams) == 1
    assert teams[0].pk == green_team.pk

    # nested_field by team
    teams = await acme.teams_set.filter(members__email=charlie.email)

    assert len(teams) == 1
    assert teams[0].pk == red_team.pk

    teams = await acme.teams_set.filter(members__email=brown.email)

    assert len(teams) == 1
    assert teams[0].pk == red_team.pk

    teams = await acme.teams_set.filter(members__email=monica.email)

    assert len(teams) == 1
    assert teams[0].pk == blue_team.pk

    teams = await acme.teams_set.filter(members__email=snoopy.email)

    assert len(teams) == 1
    assert teams[0].pk == blue_team.pk

    # nested_field by team_members FK
    teams = await acme.teams_set.filter(team_members__email=brown.email)

    assert len(teams) == 0

    teams = await acme.teams_set.filter(team_members__email=snoopy.email)

    assert len(teams) == 0

    teams = await acme.teams_set.filter(team_members__email=charlie.email)

    assert len(teams) == 1
    assert teams[0].pk == green_team.pk

    teams = await acme.teams_set.filter(team_members__email=monica.email)

    assert len(teams) == 1
    assert teams[0].pk == green_team.pk

    teams = await acme.teams_set.filter(team_members__name__icontains=monica.name)

    assert len(teams) == 1
    assert teams[0].pk == green_team.pk

    teams = await acme.teams_set.filter(team_members__name__icontains=snoopy.name)

    assert len(teams) == 0

    # Using distinct
    teams = await acme.teams_set.filter(team_members__id__in=[monica.pk, charlie.pk]).distinct(
        "name"
    )

    assert len(teams) == 1
    assert teams[0].pk == green_team.pk


async def test_nested_related_query():
    acme = await Organisation.query.create(ident="ACME Ltd")
    red_team = await Team.query.create(org=acme, name="Red Team")
    green_team = await Team.query.create(org=acme, name="Green Team")

    # members
    charlie = await Member.query.create(
        team=red_team, email="charlie@redteam.com", second_team=green_team, name="Charlie"
    )

    user = await User.query.create(member=charlie, name="Saffier")

    teams = await acme.teams_set.filter(
        members__email=charlie.email, members__users__name=user.name
    )

    assert len(teams) == 1
    assert teams[0].pk == red_team.pk

    # another member
    monica = await Member.query.create(
        team=green_team, email="monica@greenteam.com", second_team=red_team, name="Monica"
    )
    user = await User.query.create(member=monica, name="New Saffier")

    teams = await acme.teams_set.filter(
        members__email=monica.email, members__users__name=user.name
    )

    assert len(teams) == 1
    assert teams[0].pk == green_team.pk

    # more nested
    profile = await Profile.query.create(user=user, profile_type="admin")

    teams = await acme.teams_set.filter(
        members__email=monica.email,
        members__users__name=user.name,
        members__users__profiles__profile_type=profile.profile_type,
    )

    assert len(teams) == 1
    assert teams[0].pk == green_team.pk
