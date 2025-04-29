import os
import sys
from asyncio import run
from pathlib import Path

import pytest

import edgy
from edgy.testing.client import DatabaseTestClient
from tests.cli.utils import arun_cmd
from tests.settings import TEST_DATABASE

pytestmark = pytest.mark.anyio

base_path = Path(os.path.abspath(__file__)).absolute().parent
outer_database = DatabaseTestClient(
    TEST_DATABASE, use_existing=False, drop_database=True, test_prefix=""
)

async def recreate_db():
    if await outer_database.is_database_exist():
        await outer_database.drop_database(outer_database.url)
    await outer_database.create_database(outer_database.url)


@pytest.fixture(scope="function", autouse=True)
async def cleanup_prepare_db():
    async with outer_database:
        yield



async def test_lazy_evaluation_no_registry():

    (o, e, ss) = await arun_cmd(
        "tests.cli.main",
        f"python {__file__} check_no_registry",
        extra_env={
            "EDGY_SETTINGS_MODULE": "tests.settings.multidb.TestSettings",
            "TEST_NO_REGISTRY_SET": "true",
            "TEST_NO_CONTENT_TYPE": "true"
        },
    )
    assert ss == 0

async def test_lazy_evaluation_with_registry():

    (o, e, ss) = await arun_cmd(
        "tests.cli.main",
        f"python {__file__} check_with_registry",
        extra_env={
            "EDGY_SETTINGS_MODULE": "tests.settings.multidb.TestSettings",
        },
    )
    assert ss == 0


async def main():
    if sys.argv[1] == "check_no_registry":
        assert not edgy.monkay.settings_evaluated
        from tests.cli import main as main  # noqa
        assert not edgy.monkay.settings_evaluated
    elif sys.argv[1] == "check_with_registry":
        assert not edgy.monkay.settings_evaluated
        from tests.cli import main as main  # noqa
        assert not edgy.monkay.settings_evaluated
        main.models.refresh_metadata()
        assert edgy.monkay.settings_evaluated

if __name__ == "__main__":
    run(main())
