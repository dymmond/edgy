import secrets
from hashlib import pbkdf2_hmac

import pytest
import sqlalchemy
from pydantic import ValidationError, model_validator

import edgy
from edgy.core.db.fields import (
    PasswordField,
)
from edgy.core.db.fields.base import BaseField
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio
database = DatabaseTestClient(DATABASE_URL, drop_database=True, use_existing=False)
models = edgy.Registry(database=database)


class SampleHasher:
    def derive(self, password: str, iterations: int = 10):
        assert not password.startswith("pbkdf2")
        # the default is not secure
        return f"pbkdf2:{iterations}:{pbkdf2_hmac('sha256', password.encode(), salt=b'', iterations=iterations).hex()}"

    def compare_pw(self, hash: str, password: str):
        algo, iterations, _ = hash.split(":", 2)
        # this is not secure
        derived = self.derive(password, int(iterations))
        return hash == derived


hasher = SampleHasher()


class MyModel(edgy.StrictModel):
    pw = edgy.PasswordField(null=False, derive_fn=hasher.derive)
    token = edgy.PasswordField(null=False, default=secrets.token_hex)

    @model_validator(mode="after")
    def not_saffier(self) -> str:
        if self.pw_original == "saffier":
            raise ValueError("must not be saffier")
        return self

    class Meta:
        registry = models


@pytest.fixture(autouse=True, scope="function")
async def create_test_database():
    async with models:
        await models.create_all()
        yield
        if not database.drop:
            await models.drop_all()


def test_can_create_password_field():
    field = PasswordField(derive_fn=hasher.derive)

    assert isinstance(field, BaseField)
    assert field.min_length is None
    assert field.max_length == 255
    assert field.null is False
    assert field.secret is True
    assert field.is_required()
    columns = field.get_columns("foo")
    assert len(columns) == 1
    assert columns[0].type.__class__ == sqlalchemy.String


def test_can_create_password_field2():
    field = PasswordField(null=True, max_length=None, secret=False, derive_fn=hasher.derive)

    assert isinstance(field, BaseField)
    assert field.min_length is None
    assert field.max_length is None
    assert field.null is True
    assert field.secret is False
    assert not field.is_required()
    columns = field.get_columns("foo")
    assert len(columns) == 1
    assert columns[0].type.__class__ == sqlalchemy.Text


async def test_pw_field_create_pw():
    obj = await MyModel.query.create(pw="test")
    assert not secrets.compare_digest(obj.pw, "test")
    assert hasher.compare_pw(obj.pw, "test")
    obj.pw = "foobar"
    assert obj.pw != "foobar"
    assert obj.pw_original == "foobar"
    with pytest.raises(ValueError):
        obj.pw = ["foobar2", "test"]
    assert obj.pw_original == "foobar"

    await obj.save()
    assert obj.pw_original is None
    assert hasher.compare_pw(obj.pw, "foobar")


async def test_pw_field_create_token_and_validate():
    obj = await MyModel.query.create(pw="test", token="234")
    assert secrets.compare_digest(obj.token, "234")
    obj.pw = ("foobar", "foobar")
    assert obj.pw != "foobar"
    assert obj.pw_original == "foobar"
    await obj.save()
    assert obj.pw_original is None


async def test_pw_field_create_fail():
    with pytest.raises(ValueError):
        await MyModel.query.create(pw=("test", "foobar"))


async def test_pw_field_create_fail_validator():
    with pytest.raises(ValidationError):
        await MyModel.query.create(pw=("saffier", "saffier"))
