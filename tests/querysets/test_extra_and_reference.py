import warnings

import pytest
import sqlalchemy
from sqlalchemy import exc, func

import edgy
from edgy.core.utils.db import hash_tablekey
from edgy.testing.client import DatabaseTestClient
from edgy.testing.factory import FactoryField, ModelFactory
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=edgy.Database(database, force_rollback=True))

pytestmark = pytest.mark.anyio


class User(edgy.StrictModel):
    name = edgy.CharField(max_length=100)
    number = edgy.fields.IntegerField()
    profile_name = edgy.fields.PlaceholderField(null=True)

    class Meta:
        registry = models


class Profile(edgy.Model):
    user = edgy.fields.OneToOne(User, related_name="profile")
    name = edgy.CharField(max_length=100)

    class Meta:
        registry = models


class SuperProfile(edgy.Model):
    profile = edgy.fields.OneToOne(Profile, related_name="profile")
    name = edgy.CharField(max_length=100)

    class Meta:
        registry = models


class UserFactory(ModelFactory):
    class Meta:
        model = User

    name = FactoryField(callback="name")


class ProfileFactory(ModelFactory):
    class Meta:
        model = Profile

    name = FactoryField(callback="name")
    user = UserFactory(number=10).to_factory_field()


class SuperProfileFactory(ModelFactory):
    class Meta:
        model = SuperProfile

    name = FactoryField(callback="name")
    profile = ProfileFactory().to_factory_field()


@pytest.fixture(autouse=True, scope="module")
async def create_test_database():
    async with database:
        await models.create_all()
        yield
        if not database.drop:
            await models.drop_all()


@pytest.fixture(autouse=True, scope="function")
async def rollback_transactions():
    async with models:
        for i in range(10):  # noqa
            await SuperProfileFactory().build().save()
        yield


async def test_basic_referencing_relaxed_related():
    for profile in await SuperProfile.query.select_related("profile").reference_select(
        {"profile": {"profile_name": "name"}}
    ):
        assert profile.profile.profile_name == profile.name


async def test_annotate_parent_manual():
    table_prefix = hash_tablekey(tablekey=User.table.key, prefix="user")
    for profile in await Profile.query.select_related("user").reference_select(
        {"user_name": f"{table_prefix}_name"}
    ):
        assert profile.user_name == profile.user.name


async def test_annotate_parent():
    for profile in await Profile.query.select_related("user").reference_select(
        {"user_name": "user__name"}
    ):
        assert profile.user_name == profile.user.name


async def test_basic_referencing_relaxed_fk():
    for profile in await SuperProfile.query.reference_select(
        {"profile": {"profile_name": "name"}}
    ):
        assert profile.profile.profile_name == profile.name


async def test_basic_referencing_strict_related():
    for profile in await Profile.query.select_related("user").reference_select(
        {"user": {"profile_name": "name"}}
    ):
        assert profile.user.profile_name == profile.name


async def test_basic_referencing_strict_fk():
    for profile in await Profile.query.reference_select({"user": {"profile_name": "name"}}):
        assert profile.user.profile_name == profile.name


async def test_overwrite():
    for profile in await Profile.query.select_related("user").reference_select(
        {"user": {"name": "name"}}
    ):
        assert profile.user.name == profile.name


async def test_counting():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", exc.SAWarning)
        for profile in await Profile.query.extra_select(
            sqlalchemy.select(func.count(User.table.c.id).label("total_number")).subquery()
        ).reference_select({"total_number": "total_number"}):
            assert profile.total_number == 10


async def test_counting_query():
    for profile in await Profile.query.extra_select(
        func.count()
        .select()
        .select_from((await User.query.as_select()).subquery())
        .label("total_number")
    ).reference_select({"total_number": "total_number"}):
        assert profile.total_number == 10


async def test_summing():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", exc.SAWarning)
        for profile in await Profile.query.extra_select(
            sqlalchemy.select(func.sum(User.table.c.number).label("total_number")).subquery()
        ).reference_select({"total_number": "total_number"}):
            assert profile.total_number == 100
