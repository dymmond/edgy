import pytest

import edgy
from edgy.testing.client import DatabaseTestClient
from edgy.testing.factory import FactoryField, ModelFactory
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=edgy.Database(database, force_rollback=True))

pytestmark = pytest.mark.anyio


class User(edgy.Model):
    name = edgy.CharField(max_length=100)
    number = edgy.fields.IntegerField()

    class Meta:
        registry = models


class Profile(edgy.Model):
    user = edgy.fields.OneToOne(User, related_name="profile")
    name = edgy.CharField(max_length=100)
    profile = edgy.fields.OneToOne(
        "SuperProfile", related_name="profile", embed_parent=("user", "normal_profile")
    )

    class Meta:
        registry = models


class SuperProfile(edgy.Model):
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
    async with models.database:
        for i in range(10):  # noqa
            await SuperProfileFactory().build().save()
        yield


async def test_embed():
    for profile in await SuperProfile.query.all():
        user = (
            await profile.profile.select_related("user")
            .reference_select({"user": {"profile_name": "name"}})
            .get()
        )
        assert isinstance(user, User)
        assert user.normal_profile.name == user.profile_name
