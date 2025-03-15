import contextlib
import decimal
import os
import shutil
import sys
from asyncio import run
from pathlib import Path

import pytest
import sqlalchemy
from sqlalchemy.ext.asyncio import create_async_engine

from tests.cli.utils import arun_cmd
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio

base_path = Path(os.path.abspath(__file__)).absolute().parent


@pytest.fixture(scope="function", autouse=True)
def cleanup_folders():
    with contextlib.suppress(OSError):
        shutil.rmtree(str(base_path / "migrations"))
    with contextlib.suppress(OSError):
        shutil.rmtree(str(base_path / "migrations2"))

    yield
    with contextlib.suppress(OSError):
        shutil.rmtree(str(base_path / "migrations"))
    with contextlib.suppress(OSError):
        shutil.rmtree(str(base_path / "migrations2"))


async def recreate_db():
    engine = create_async_engine(DATABASE_URL, isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as conn:
            await conn.execute(sqlalchemy.text("DROP DATABASE test_edgy"))
    except Exception:
        pass
    async with engine.connect() as conn:
        await conn.execute(sqlalchemy.text("CREATE DATABASE test_edgy"))


@pytest.fixture(scope="function", autouse=True)
async def cleanup_prepare_db():
    await recreate_db()


@pytest.mark.parametrize(
    "template_param",
    ["", " -t default", " -t plain", " -t url"],
    ids=["default_empty", "default", "plain", "url"],
)
async def test_migrate_server_defaults_upgrade(template_param):
    os.chdir(base_path)
    assert not (base_path / "migrations").exists()
    (o, e, ss) = await arun_cmd(
        "tests.cli.main_server_defaults",
        f"edgy init{template_param}",
    )
    assert ss == 0

    (o, e, ss) = await arun_cmd(
        "tests.cli.main_server_defaults", "edgy makemigrations"
    )
    assert ss == 0
    assert b"No changes in schema detected" not in o

    (o, e, ss) = await arun_cmd(
        "tests.cli.main_server_defaults", "edgy migrate"
    )
    assert ss == 0

    (o, e, ss) = await arun_cmd(
        "tests.cli.main_server_defaults",
        f"python {__file__} add",
        with_app_environment=False,
        extra_env={
            "EDGY_SETTINGS_MODULE": "tests.settings.multidb.TestSettings",
        },
    )
    assert ss == 0

    (o, e, ss) = await arun_cmd(
        "tests.cli.main_server_defaults",
        "edgy makemigrations",
        extra_env={"TEST_ADD_AUTO_SERVER_DEFAULTS": "true"},
    )

    (o, e, ss) = await arun_cmd(
        "tests.cli.main_server_defaults", "edgy migrate", extra_env={"TEST_ADD_AUTO_SERVER_DEFAULTS": "true"}
    )
    assert ss == 0

    (o, e, ss) = await arun_cmd(
        "tests.cli.main_server_defaults",
        f"python {__file__} add2",
        extra_env={
            "EDGY_SETTINGS_MODULE": "tests.settings.multidb.TestSettings",
            "TEST_ADD_AUTO_SERVER_DEFAULTS": "true",
        },
    )
    assert ss == 0
    (o, e, ss) = await arun_cmd(
        "tests.cli.main_server_defaults",
        f"python {__file__} check",
        with_app_environment=False,
        extra_env={
            "EDGY_SETTINGS_MODULE": "tests.settings.multidb.TestSettings",
            "TEST_ADD_AUTO_SERVER_DEFAULTS": "true",
        },
    )
    assert ss == 0

    migrations = list((base_path / "migrations" / "versions").glob("*.py"))
    assert len(migrations) == 2

async def main():
    if sys.argv[1] == "add":
        from tests.cli import main_server_defaults as main

        async with main.models:
            user = await main.User.query.create(name="edgy")
    elif sys.argv[1] == "add2":
        from tests.cli import main_server_defaults as main

        async with main.models:
            user = await main.User.query.create(name="edgy2", active=False)
    elif sys.argv[1] == "check":
        from tests.cli import main_server_defaults as main

        async with main.models:
            user = await main.User.query.get(name="edgy")
            assert user.active
            assert not user.is_staff
            assert user.age == 18
            assert user.size == decimal.Decimal("1.8")
            assert user.blob == b"abc"
            assert user.data == {"test": "test"}
            # assert user.user_type == main.UserTypeEnum.INTERNAL
            assert user.content_type.name == "User"

            user2 = await main.User.query.get(name="edgy2")
            assert not user2.active
            assert user.content_type.name == "User"
if __name__ == "__main__":
    run(main())
