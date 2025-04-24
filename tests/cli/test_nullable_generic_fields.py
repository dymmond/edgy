import contextlib
import os
import shutil
import sys
from asyncio import run
from pathlib import Path

import pytest

from edgy.testing.client import DatabaseTestClient
from tests.cli.utils import arun_cmd
from tests.settings import TEST_DATABASE

pytestmark = pytest.mark.anyio

base_path = Path(os.path.abspath(__file__)).absolute().parent
outer_database = DatabaseTestClient(
    TEST_DATABASE, use_existing=False, drop_database=True, test_prefix=""
)


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
    if await outer_database.is_database_exist():
        await outer_database.drop_database(outer_database.url)
    await outer_database.create_database(outer_database.url)


@pytest.fixture(scope="function", autouse=True)
async def cleanup_prepare_db():
    async with outer_database:
        yield


@pytest.mark.parametrize(
    "template_param",
    ["", " -t default", " -t plain", " -t url"],
    ids=["default_empty", "default", "plain", "url"],
)
async def test_migrate_nullable_upgrade(template_param):
    os.chdir(base_path)
    assert not (base_path / "migrations").exists()
    (o, e, ss) = await arun_cmd(
        "tests.cli.main",
        f"edgy init{template_param}",
    )
    assert ss == 0

    (o, e, ss) = await arun_cmd(
        "tests.cli.main",
        "edgy makemigrations",
        extra_env={
            "TEST_NO_CONTENT_TYPE": "true",
            "TEST_ADD_NULLABLE_FIELDS": "true",
            "TEST_ADD_SIGNALS": "true",
        },
    )
    assert ss == 0
    assert b"No changes in schema detected" not in o
    assert b"abc start revision" in o

    (o, e, ss) = await arun_cmd(
        "tests.cli.main",
        "edgy migrate",
        extra_env={
            "TEST_NO_CONTENT_TYPE": "true",
            "TEST_ADD_NULLABLE_FIELDS": "true",
            "TEST_ADD_SIGNALS": "true",
        },
    )
    assert ss == 0

    (o, e, ss) = await arun_cmd(
        "tests.cli.main",
        f"python {__file__} add",
        extra_env={
            "EDGY_SETTINGS_MODULE": "tests.settings.multidb.TestSettings",
            "TEST_NO_CONTENT_TYPE": "true",
            "TEST_ADD_NULLABLE_FIELDS": "true",
            "TEST_ADD_SIGNALS": "true",
        },
    )
    assert ss == 0

    (o, e, ss) = await arun_cmd(
        "tests.cli.main",
        "edgy makemigrations --null-field :content_type",
        extra_env={"TEST_ADD_NULLABLE_FIELDS": "true"},
    )

    (o, e, ss) = await arun_cmd(
        "tests.cli.main",
        "edgy migrate",
        extra_env={"TEST_ADD_NULLABLE_FIELDS": "true", "TEST_ADD_SIGNALS": "true"},
    )
    assert ss == 0

    (o, e, ss) = await arun_cmd(
        "tests.cli.main",
        f"python {__file__} check",
        extra_env={
            "EDGY_SETTINGS_MODULE": "tests.settings.multidb.TestSettings",
            "TEST_ADD_NULLABLE_FIELDS": "true",
            "TEST_ADD_SIGNALS": "true",
        },
    )
    assert ss == 0


async def main():
    if sys.argv[1] == "add":
        from tests.cli import main

        async with main.models:
            user = await main.User.query.create(name="edgy")
    elif sys.argv[1] == "check":
        from tests.cli import main

        async with main.models:
            assert await main.User.query.exists(name="migration_user")
            user = await main.User.query.get(name="edgy")
            assert user.content_type.name == "User"
            assert user.profile.content_type.name == "Profile"


if __name__ == "__main__":
    run(main())
