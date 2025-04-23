from contextlib import asynccontextmanager

import pytest
from monkay import Monkay

import edgy
from edgy.contrib.permissions import BasePermission
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio

database = DatabaseTestClient(DATABASE_URL, use_existing=False)
models = edgy.Registry(database=edgy.Database(database, force_rollback=True))


class PermissionExtension:
    name: str = "permissions-test"

    def apply(self, value: Monkay):
        class User(edgy.StrictModel):
            name = edgy.fields.CharField(max_length=100, unique=True)

            class Meta:
                registry = value.instance.registry

        class Permission(BasePermission):
            users = edgy.fields.ManyToMany("User", through_tablename=edgy.NEW_M2M_NAMING)

            class Meta:
                registry = value.instance.registry
                unique_together = [("name",)]


@asynccontextmanager
async def create_test_database():
    async with database:
        await models.create_all()
        async with models:
            yield
        if not database.drop:
            await models.drop_all()
        # clear the registry
        models.models.clear()


async def test_extensions_add_extension():
    with edgy.monkay.with_extensions({}) as extensions:
        edgy.monkay.add_extension(PermissionExtension)
        assert "permissions-test" in extensions
        with edgy.monkay.with_instance(edgy.Instance(models), apply_extensions=True):
            async with create_test_database():
                User = models.get_model("User")
                Permission = models.get_model("Permission")
                user = await User.query.create(name="edgy")
                permission = await Permission.query.create(users=[user], name="view")
                assert await Permission.query.users("view").get() == user
                assert await Permission.query.users("edit").count() == 0
                assert await Permission.query.permissions_of(user).get() == permission


async def test_extensions_extension_settings():
    with (
        edgy.monkay.with_settings(
            edgy.settings.model_copy(update={"extensions": [PermissionExtension]})
        ),
        edgy.monkay.with_extensions({}) as extensions,
    ):
        assert "permissions-test" not in extensions
        edgy.monkay.evaluate_settings(on_conflict="error")
        assert "permissions-test" in extensions
        with edgy.monkay.with_instance(edgy.Instance(models), apply_extensions=True):
            async with create_test_database():
                User = models.get_model("User")
                Permission = models.get_model("Permission")
                user = await User.query.create(name="edgy")
                permission = await Permission.query.create(users=[user], name="view")
                assert await Permission.query.users("view").get() == user
                assert await Permission.query.users("edit").count() == 0
                assert await Permission.query.permissions_of(user).get() == permission
