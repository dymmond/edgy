import edgy
from edgy import Database, Registry

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


class Organisation(edgy.Model):
    ident: str = edgy.CharField(max_length=100)

    class Meta:
        registry = models


class Team(edgy.Model):
    org: Organisation = edgy.ForeignKey(Organisation, on_delete=edgy.RESTRICT)
    name: str = edgy.CharField(max_length=100)

    class Meta:
        registry = models


class Member(edgy.Model):
    team: Team = edgy.ForeignKey(Team, on_delete=edgy.SET_NULL, null=True, related_name="members")
    second_team: Team = edgy.ForeignKey(
        Team, on_delete=edgy.SET_NULL, null=True, related_name="team_members"
    )
    email: str = edgy.CharField(max_length=100)
    name: str = edgy.CharField(max_length=255, null=True)

    class Meta:
        registry = models


class User(edgy.Model):
    name: str = edgy.CharField(max_length=255, null=True)
    member: Member = edgy.ForeignKey(
        Member, on_delete=edgy.SET_NULL, null=True, related_name="users"
    )

    class Meta:
        registry = models


class Profile(edgy.Model):
    user: User = edgy.ForeignKey(User, on_delete=edgy.CASCADE, null=False, related_name="profiles")
    profile_type: str = edgy.CharField(max_length=255, null=False)

    class Meta:
        registry = models
