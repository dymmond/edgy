import edgy
from edgy import Database, Registry

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


class Organisation(edgy.Model):
    ident = edgy.CharField(max_length=100)

    class Meta:
        registry = models


class Team(edgy.Model):
    org = edgy.ForeignKey(Organisation, on_delete=edgy.RESTRICT)
    name = edgy.CharField(max_length=100)

    class Meta:
        registry = models


class Member(edgy.Model):
    team = edgy.ForeignKey(Team, on_delete=edgy.SET_NULL, null=True, related_name="members")
    second_team = edgy.ForeignKey(
        Team, on_delete=edgy.SET_NULL, null=True, related_name="team_members"
    )
    email = edgy.CharField(max_length=100)
    name = edgy.CharField(max_length=255, null=True)

    class Meta:
        registry = models
