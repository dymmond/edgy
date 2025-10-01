import asyncio
import sys
from shutil import rmtree

import pytest
from monkay import ExtensionProtocol

import edgy
from edgy import EdgySettings, Registry
from edgy.cli.base import init, revision, upgrade
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database_outer = DatabaseTestClient(
    url=DATABASE_URL,
    force_rollback=False,
    drop_database=True,
    use_existing=False,
)
database = edgy.Database(database_outer)
pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True, scope="function")
async def cleanup_db():
    rmtree("test_migrations", ignore_errors=True)
    async with database_outer:
        yield
    rmtree("test_migrations", ignore_errors=True)


class User(edgy.Model):
    age: int = edgy.IntegerField(gte=18)
    is_active: bool = edgy.BooleanField(default=True)


class AddUserExtension(ExtensionProtocol):
    name = "add_user"

    def apply(self, monkay_instance):
        UserCopy = User.copy_edgy_model()
        UserCopy.add_to_registry(monkay_instance.instance.registry, name="User")


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
            edgy.monkay.with_instance(edgy.Instance(Registry(database)), apply_extensions=False),
        ):
            edgy.monkay.evaluate_settings()
            edgy.monkay.apply_extensions()
            assert "User" in edgy.monkay.instance.registry.models
            await asyncio.to_thread(init)
            await asyncio.to_thread(revision, autogenerate=True)
            if with_upgrade:
                await asyncio.to_thread(upgrade)


def prepare(with_upgrade: bool):
    asyncio.run(_prepare(with_upgrade))


@pytest.mark.parametrize("run", [1, 2])
async def test_automigrate_manual(run):
    subprocess = await asyncio.create_subprocess_exec(sys.executable, __file__, "prepare", "true")
    await subprocess.communicate()
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
    await subprocess.communicate()
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
    await subprocess.communicate()
    with edgy.monkay.with_settings(Config(allow_automigrations=False)):
        async with create_registry(database) as registry:
            assert "User" not in registry.models
            assert "users" not in registry.metadata_by_name[None].tables


if __name__ == "__main__":  # noqa: SIM102
    if sys.argv[1] == "prepare":
        prepare(sys.argv[2] == "true")
