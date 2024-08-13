from typing import Any

import pytest

import edgy
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=database)

pytestmark = pytest.mark.anyio


class User(edgy.Model):
    id = edgy.IntegerField(primary_key=True)
    name = edgy.CharField(max_length=100)
    language = edgy.CharField(max_length=200, null=True)
    description = edgy.TextField(max_length=5000, null=True)

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


@pytest.fixture(autouse=True, scope="function")
async def create_test_database():
    await models.create_all()
    yield
    await models.drop_all()


@pytest.fixture(autouse=True)
async def rollback_connections():
    with database.force_rollback():
        async with database:
            yield


async def test_model_fields_are_different():
    user = await User.query.create(name="John", language="PT", description="John")

    assert user.model_fields["name"].annotation is str
    assert User.model_fields["name"].annotation is str

    assert user.proxy_model.model_fields["name"].annotation is Any
    assert User.proxy_model.model_fields["name"].annotation is Any
