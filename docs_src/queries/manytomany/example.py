import edgy
from edgy import Database, Registry

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


class Team(edgy.Model):
    name = edgy.CharField(max_length=100)

    class Meta:
        registry = models


class Organisation(edgy.Model):
    ident = edgy.CharField(max_length=100)
    teams = edgy.ManyToManyField(Team, related_name="organisation_teams")

    class Meta:
        registry = models
