import contextlib
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


@pytest.fixture(scope="function", autouse=True)
async def cleanup_prepare_db():
    engine = create_async_engine(DATABASE_URL, isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as conn:
            await conn.execute(sqlalchemy.text("DROP DATABASE test_edgy"))
    except Exception:
        pass
    async with engine.connect() as conn:
        await conn.execute(sqlalchemy.text("CREATE DATABASE test_edgy"))


@pytest.mark.parametrize("app_flag", ["explicit", "explicit_env", "autosearch"])
@pytest.mark.parametrize(
    "template_param",
    ["", " -t default", " -t plain", " -t url", " -t ./custom_singledb"],
    ids=["default_empty", "default", "plain", "url", "custom"],
)
async def test_migrate_upgrade(app_flag, template_param):
    os.chdir(base_path)
    assert not (base_path / "migrations").exists()
    app_param = "--app tests.cli.main " if app_flag == "explicit" else ""
    (o, e, ss) = await arun_cmd(
        "tests.cli.main",
        f"edgy {app_param}init{template_param}",
        with_app_environment=app_flag == "explicit_env",
    )
    assert ss == 0

    (o, e, ss) = await arun_cmd(
        "tests.cli.main",
        f"edgy {app_param}makemigrations",
        with_app_environment=app_flag == "explicit_env",
    )
    assert ss == 0
    assert b"No changes in schema detected" not in o

    (o, e, ss) = await arun_cmd(
        "tests.cli.main",
        f"edgy {app_param}migrate",
        with_app_environment=app_flag == "explicit_env",
    )
    assert ss == 0

    (o, e, ss) = await arun_cmd(
        "tests.cli.main",
        f"hatch run python {__file__} test_migrate_upgrade",
        with_app_environment=False,
        extra_env={"EDGY_SETTINGS_MODULE": "tests.settings.multidb.TestSettings"},
    )
    assert ss == 0

    if "custom" in template_param:
        with open("migrations/README") as f:
            assert f.readline().strip() == "Custom template"
        with open("migrations/alembic.ini") as f:
            assert f.readline().strip() == "# A custom generic database configuration."
        with open("migrations/env.py") as f:
            assert f.readline().strip() == "# Custom env template"
        with open("migrations/script.py.mako") as f:
            assert f.readline().strip() == "# Custom mako template"
    else:
        with open("migrations/README") as f:
            assert f.readline().strip() == "Database configuration with Alembic."
        with open("migrations/alembic.ini") as f:
            assert f.readline().strip() == "# A generic database configuration."
        with open("migrations/env.py") as f:
            assert f.readline().strip() == "# Default env template"


@pytest.mark.parametrize("app_flag", ["explicit", "explicit_env", "autosearch"])
@pytest.mark.parametrize(
    "template_param",
    ["", " -t default", " -t plain", " -t url", " -t ./custom_singledb"],
    ids=["default_empty", "default", "plain", "url", "custom"],
)
async def test_different_directory(app_flag, template_param):
    os.chdir(base_path)
    assert not (base_path / "migrations2").exists()
    app_param = "--app tests.cli.main " if app_flag == "explicit" else ""
    (o, e, ss) = await arun_cmd(
        "tests.cli.main",
        f"edgy {app_param}init -d migrations2 {template_param}",
        with_app_environment=app_flag == "explicit_env",
    )

    (o, e, ss) = await arun_cmd(
        "tests.cli.main",
        f"edgy {app_param}makemigrations -d migrations2",
        with_app_environment=app_flag == "explicit_env",
    )
    assert ss == 0
    assert b"No changes in schema detected" not in o
    if "custom" in template_param:
        with open("migrations2/README") as f:
            assert f.readline().strip() == "Custom template"
        with open("migrations2/alembic.ini") as f:
            assert f.readline().strip() == "# A custom generic database configuration."
        with open("migrations2/env.py") as f:
            assert f.readline().strip() == "# Custom env template"
        with open("migrations2/script.py.mako") as f:
            assert f.readline().strip() == "# Custom mako template"
    else:
        with open("migrations2/README") as f:
            assert f.readline().strip() == "Database configuration with Alembic."
        with open("migrations2/alembic.ini") as f:
            assert f.readline().strip() == "# A generic database configuration."
        with open("migrations2/env.py") as f:
            assert f.readline().strip() == "# Default env template"


async def main():
    if sys.argv[1] == "test_migrate_upgrade":
        from tests.cli import main

        async with main.models:
            user = await main.User.query.create(name="edgy")
            permission = await main.Permission.query.create(users=[user], name="view")
            assert await main.Permission.query.users("view").get() == user
            assert await main.Permission.query.permissions_of(user).get() == permission


if __name__ == "__main__":
    run(main())
