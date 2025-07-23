import pytest
from pydantic import ValidationError

import edgy
from edgy.core.db.fields.base import Field
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL, force_rollback=False)
models = edgy.Registry(database=database)

pytestmark = pytest.mark.anyio


class User(edgy.StrictModel):
    id: int = edgy.IntegerField(primary_key=True, autoincrement=True)
    name: str = ""

    class Meta:
        registry = models


@pytest.fixture()
async def create_test_database():
    await models.create_all()
    async with models:
        yield
    if not database.drop:
        await models.drop_all()


def test_model_class():
    assert sorted(User.meta.fields.keys()) == sorted(["pk", "id"])
    assert isinstance(User.meta.fields["id"], Field)
    assert User.meta.fields["id"] is User.model_fields["id"]
    assert User.meta.fields["id"].primary_key is True
    assert "name" not in User.meta.fields
    assert not isinstance(User.model_fields["name"], Field)
    with pytest.raises(ValidationError):
        User(name=83)

    assert User(id=1, name="test").name == "test"

    assert str(User(id=1)) == "User(id=1)"
    assert repr(User(id=1)) == "<User: User(id=1)>"


async def test_create(create_test_database):
    user = await User.query.create()
    assert user.name == ""


async def test_save(create_test_database):
    user = await User().save()
    assert user.name == ""
