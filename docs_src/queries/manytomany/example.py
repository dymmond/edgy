from typing import List

import edgy
from edgy import Database, Registry

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


class Team(edgy.Model):
    name: str = edgy.CharField(max_length=100)

    class Meta:
        registry = models


class Organisation(edgy.Model):
    ident: str = edgy.CharField(max_length=100)
    # through_tablename=edgy.NEW_M2M_NAMING is now optional
    teams: List[Team] = edgy.ManyToManyField(Team, related_name="organisation_teams")

    class Meta:
        registry = models
