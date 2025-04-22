from datetime import date
from typing import ClassVar

import pytest

import edgy
from edgy import Manager
from edgy.core.db.querysets import QuerySet
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=edgy.Database(database, force_rollback=True))

pytestmark = pytest.mark.anyio


class UserManager(Manager):
    def get_queryset(self) -> QuerySet:
        queryset = super().get_queryset().filter(is_admin=False)
        return queryset


class User(edgy.StrictModel):
    password: str = edgy.CharField(max_length=128)
    username: str = edgy.CharField(max_length=150, unique=True)
    email: str = edgy.EmailField(max_length=120, unique=True)
    is_active: bool = edgy.BooleanField(default=True)
    is_student: bool = edgy.BooleanField(default=True)
    is_teacher: bool = edgy.BooleanField(default=True)
    is_admin: bool = edgy.BooleanField(default=True)
    is_staff: bool = edgy.BooleanField(default=False)
    created_at: date = edgy.DateField(auto_now_add=True)

    mang: ClassVar[Manager] = UserManager()

    class Meta:
        registry = models


@pytest.fixture(autouse=True, scope="module")
async def create_test_database():
    await models.create_all()
    yield
    if not database.drop:
        await models.drop_all()


@pytest.fixture(autouse=True, scope="function")
async def rollback_transactions():
    with models.database.force_rollback(True):
        async with models:
            yield


async def test_can_create_record():
    await User.mang.create(password="12345", username="user", email="test@test.com")
    assert User.mang.instance is None

    users = await User.mang.all()

    assert len(users) == 0

    user = await User.mang.create(
        password="12345", username="user2", email="test1@test.com", is_admin=False
    )
    assert user.mang.instance is user
    User.mang._fooobar = True
    assert hasattr(User.mang, "_fooobar")
    assert not hasattr(user.mang, "_fooobar")

    users = await User.mang.all()

    assert len(users) == 1
    assert users[0].pk == user.pk
    # new instances have now the attribute
    assert hasattr(users[0].mang, "_fooobar")
