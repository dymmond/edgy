from datetime import date
from typing import ClassVar

import pytest

import edgy
from edgy import Manager
from edgy.core.db.querysets import QuerySet
from edgy.testclient import DatabaseTestClient as Database
from tests.settings import DATABASE_URL

database = Database(url=DATABASE_URL)
models = edgy.Registry(database=database)

pytestmark = pytest.mark.anyio


class UserManager(Manager):
    def get_queryset(self) -> QuerySet:
        queryset = super().get_queryset().filter(is_admin=False)
        return queryset


class User(edgy.Model):
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


async def test_can_create_record():
    await User.mang.create(password="12345", username="user", email="test@test.com")

    users = await User.mang.all()

    assert len(users) == 0

    user = await User.mang.create(password="12345", username="user2", email="test1@test.com", is_admin=False)

    users = await User.mang.all()

    assert len(users) == 1
    assert users[0].pk == user.pk
