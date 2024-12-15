from typing import List

import edgy
from edgy import Database, Registry

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


class Team(edgy.Model):
    name: str = edgy.fields.CharField(max_length=100)

    class Meta:
        registry = models


class TeamMember(edgy.Model):
    name: str = edgy.fields.CharField(max_length=100)
    team: Team = edgy.fields.ForeignKey(Team, related_name="members")

    class Meta:
        registry = models
