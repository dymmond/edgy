import asyncio
import sys
from contextlib import suppress
from shutil import rmtree

import pytest
from monkay import ExtensionProtocol

import edgy
from edgy import EdgySettings, Registry
from edgy.cli.base import init, migrate, upgrade
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(
    url=DATABASE_URL,
    force_rollback=False,
    drop_database=False,
    use_existing=True,
)
pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True, scope="function")
async def cleanup_db():
    rmtree("test_migrations", ignore_errors=True)
    await asyncio.sleep(2)
    with suppress(Exception):
        await database.drop_database(database.url)
    yield
    with suppress(Exception):
        await database.drop_database(database.url)
    rmtree("test_migrations", ignore_errors=True)
    await asyncio.sleep(0.5)


class User(edgy.Model):
    age: int = edgy.IntegerField(gte=18)
    is_active: bool = edgy.BooleanField(default=True)


class AddUserExtension(ExtensionProtocol):
    name = "add_user"

    def apply(self, monkay_instance):
        UserCopy = User.copy_edgy_model()
        UserCopy.add_to_registry(monkay_instance.instance.registry)


class Config(EdgySettings):
    extensions: list = [AddUserExtension()]
    migration_directory: str = "test_migrations"


def create_registry(db):
    registry = Registry(db, automigrate_config=Config)
    assert not registry._is_automigrated
    return registry


async def _prepare(with_upgrade: bool):
    async with database:
        with (
            edgy.monkay.with_extensions({}),
            edgy.monkay.with_settings(Config()),
            edgy.monkay.with_instance(edgy.Instance(Registry(database)), apply_extensions=True),
        ):
            await asyncio.to_thread(init)
            await asyncio.to_thread(migrate)
            if with_upgrade:
                await asyncio.to_thread(upgrade)


def prepare(with_upgrade: bool):
    asyncio.run(_prepare(with_upgrade))


@pytest.mark.parametrize("run", [1, 2])
async def test_automigrate_manual(run):
    subprocess = await asyncio.create_subprocess_exec(sys.executable, __file__, "prepare", "true")
    out, err = await subprocess.communicate()
    assert not err
    async with Registry(database) as registry:
        UserCopy = User.copy_edgy_model()
        UserCopy.add_to_registry(registry)
        registry.refresh_metadata()
        assert "User" in registry.models
        assert "users" in registry.metadata_by_name[None].tables
        user = await UserCopy.query.create(age=18)
        assert user.age == 18


@pytest.mark.parametrize("run", [1, 2])
async def test_automigrate_automatic(run):
    subprocess = await asyncio.create_subprocess_exec(sys.executable, __file__, "prepare", "false")
    out, err = await subprocess.communicate()
    assert not err
    async with create_registry(database) as registry:
        registry.refresh_metadata()
        assert "User" in registry.models
        assert "users" in registry.metadata_by_name[None].tables
        UserCopy = registry.get_model("User")
        assert registry.database.is_connected
        assert UserCopy.database is registry.database
        assert UserCopy.table is registry.metadata_by_name[None].tables["users"]
        query = UserCopy.query.all()
        assert query.table is registry.metadata_by_name[None].tables["users"]
        user = await UserCopy.query.create(age=18)
        assert user.age == 18


async def test_automigrate_disabled():
    subprocess = await asyncio.create_subprocess_exec(sys.executable, __file__, "prepare", "false")
    out, err = await subprocess.communicate()
    assert not err
    with edgy.monkay.with_settings(Config(allow_automigrations=False)):
        async with create_registry(database) as registry:
            assert "User" not in registry.models
            assert "users" not in registry.metadata_by_name[None].tables


if __name__ == "__main__":  # noqa: SIM102
    print("enter", sys.argv)
    if sys.argv[1] == "prepare":
        prepare(sys.argv[2] == "true")
