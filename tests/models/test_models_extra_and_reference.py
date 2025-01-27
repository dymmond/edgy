import warnings

import pytest
import sqlalchemy
from sqlalchemy import exc, func

import edgy
from edgy.testing.client import DatabaseTestClient
from edgy.testing.factory import FactoryField, ModelFactory
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL, force_rollback=True)
models = edgy.Registry(database=database)

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

    exclude_autoincrement = True
    name = FactoryField(callback="name")


class ProfileFactory(ModelFactory):
    class Meta:
        model = Profile

    exclude_autoincrement = True
    name = FactoryField(callback="name")
    user = UserFactory(number=10).to_factory_field()


class SuperProfileFactory(ModelFactory):
    class Meta:
        model = SuperProfile

    exclude_autoincrement = True
    name = FactoryField(callback="name")
    profile = ProfileFactory().to_factory_field()


@pytest.fixture(autouse=True, scope="module")
async def create_test_database():
    await models.create_all()
    yield
    if not database.drop:
        await models.drop_all()


@pytest.fixture(autouse=True, scope="function")
async def rollback_transactions():
    async with models.database:
        for i in range(10):  # noqa
            await SuperProfileFactory().build().save()
        yield


async def test_basic_referencing_relaxed_related():
    for profile in await SuperProfile.query.select_related("profile").reference_select(
        {"profile": {"profile_name": "name"}}
    ):
        assert profile.profile.profile_name == profile.name


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


async def test_summing():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", exc.SAWarning)
        for profile in await Profile.query.extra_select(
            sqlalchemy.select(func.sum(User.table.c.number).label("total_number")).subquery()
        ).reference_select({"total_number": "total_number"}):
            assert profile.total_number == 100
