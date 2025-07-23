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


async def test_migrate_json_to_jsonb():
    os.chdir(base_path)
    assert not (base_path / "migrations").exists()
    (o, e, ss) = await arun_cmd(
        "tests.cli.main_json",
        "edgy init -t default",
    )
    assert ss == 0

    (o, e, ss) = await arun_cmd(
        "tests.cli.main_json",
        "edgy makemigrations",
        extra_env={"TEST_NO_JSONB": "true"},
    )
    assert ss == 0
    assert b"No changes in schema detected" not in o

    (o, e, ss) = await arun_cmd(
        "tests.cli.main_json",
        "edgy migrate",
        extra_env={"TEST_NO_JSONB": "true"},
    )
    assert ss == 0

    (o, e, ss) = await arun_cmd(
        "tests.cli.main_json",
        f"python {__file__} add",
        extra_env={"TEST_NO_JSONB": "true"},
    )
    assert ss == 0

    (o, e, ss) = await arun_cmd(
        "tests.cli.main_json",
        f"python {__file__} check",
        extra_env={"TEST_NO_JSONB": "true"},
    )
    assert ss == 0

    (o, e, ss) = await arun_cmd(
        "tests.cli.main_json",
        "edgy makemigrations",
    )
    assert ss == 0
    assert b"No changes in schema detected" not in o

    (o, e, ss) = await arun_cmd(
        "tests.cli.main_json",
        "edgy migrate",
    )
    assert ss == 0
    (o, e, ss) = await arun_cmd(
        "tests.cli.main_json",
        f"python {__file__} add2",
    )
    assert ss == 0

    (o, e, ss) = await arun_cmd(
        "tests.cli.main_json",
        f"python {__file__} check2",
    )
    assert ss == 0


async def main():
    if sys.argv[1] == "add":
        from tests.cli import main_json

        async with main_json.models:
            user = await main_json.User.query.create(name="edgy", data={"foo": "faa"})
    if sys.argv[1] == "add2":
        from tests.cli import main_json

        async with main_json.models:
            user = await main_json.User.query.create(name="edgy2", data={"foo2": "faa"})
    elif sys.argv[1] == "check":
        from tests.cli import main_json

        async with main_json.models:
            user = await main_json.User.query.get(name="edgy")
            assert user.data == {"foo": "faa"}
    elif sys.argv[1] == "check2":
        from tests.cli import main_json

        async with main_json.models:
            user = await main_json.User.query.get(name="edgy")
            assert user.data == {"foo": "faa"}
            user = await main_json.User.query.get(name="edgy2")
            assert user.data == {"foo2": "faa"}


if __name__ == "__main__":
    run(main())
