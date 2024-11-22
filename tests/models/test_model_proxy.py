from typing import Any

import edgy
from tests.settings import DATABASE_URL

models = edgy.Registry(database=DATABASE_URL)


class User(edgy.StrictModel):
    id = edgy.IntegerField(primary_key=True, autoincrement=True)
    name = edgy.CharField(max_length=100)
    language = edgy.CharField(max_length=200, null=True)
    description = edgy.TextField(max_length=5000, null=True)

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
    team = edgy.ForeignKey(Team, on_delete=edgy.SET_NULL, null=True, related_name="members")
    second_team = edgy.ForeignKey(
        Team, on_delete=edgy.SET_NULL, null=True, related_name="team_members"
    )
    email = edgy.CharField(max_length=100)
    name = edgy.CharField(max_length=255, null=True)

    class Meta:
        registry = models


def test_model_fields_are_different():
    # since pydantic 2.10 it is deprecated to access model_fields via instance
    assert User.model_fields["name"].annotation is str

    assert User.proxy_model.model_fields["name"].annotation is Any
