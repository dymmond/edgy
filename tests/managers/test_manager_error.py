import pytest

import edgy
from edgy import Manager
from edgy.core.db.querysets import QuerySet
from edgy.exceptions import ImproperlyConfigured
from edgy.testclient import DatabaseTestClient as Database
from tests.settings import DATABASE_URL

database = Database(url=DATABASE_URL)
models = edgy.Registry(database=database)

pytestmark = pytest.mark.anyio


class UserManager(Manager):
    def get_queryset(self) -> QuerySet:
        queryset = super().get_queryset().filter(is_admin=False)
        return queryset


async def test_raise_improperly_configured_on_missing_annotation():
    with pytest.raises(ImproperlyConfigured) as raised:

        class User(edgy.Model):
            username: str = edgy.CharField(max_length=150)
            is_admin: bool = edgy.BooleanField(default=True)

            mang = UserManager()

            class Meta:
                registry = models

    assert (
        raised.value.args[0]
        == "Managers must be type annotated and 'mang' is not annotated. Managers must be annotated with ClassVar."
    )


async def test_raise_improperly_configured_on_wrong_annotation():
    with pytest.raises(ImproperlyConfigured) as raised:

        class User(edgy.Model):
            username: str = edgy.CharField(max_length=150)
            is_admin: bool = edgy.BooleanField(default=True)

            mang: Manager = UserManager()

            class Meta:
                registry = models

    assert raised.value.args[0] == "Managers must be ClassVar type annotated."
