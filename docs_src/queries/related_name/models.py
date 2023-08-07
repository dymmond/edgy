import saffier
from saffier import Database, Registry

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


class Organisation(saffier.Model):
    ident = saffier.CharField(max_length=100)

    class Meta:
        registry = models


class Team(saffier.Model):
    org = saffier.ForeignKey(Organisation, on_delete=saffier.RESTRICT)
    name = saffier.CharField(max_length=100)

    class Meta:
        registry = models


class Member(saffier.Model):
    team = saffier.ForeignKey(Team, on_delete=saffier.SET_NULL, null=True, related_name="members")
    second_team = saffier.ForeignKey(
        Team, on_delete=saffier.SET_NULL, null=True, related_name="team_members"
    )
    email = saffier.CharField(max_length=100)
    name = saffier.CharField(max_length=255, null=True)

    class Meta:
        registry = models
