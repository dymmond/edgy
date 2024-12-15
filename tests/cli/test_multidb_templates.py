import contextlib
import os
import shutil
import sys
from asyncio import run
from pathlib import Path

import pytest
import sqlalchemy
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import create_async_engine

from tests.cli.utils import arun_cmd
from tests.settings import (
    DATABASE_ALTERNATIVE_URL,
    DATABASE_URL,
    TEST_ALTERNATIVE_DATABASE,
    TEST_DATABASE,
)

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
async def prepare_db():
    for url in [DATABASE_ALTERNATIVE_URL, DATABASE_URL]:
        engine = create_async_engine(url, isolation_level="AUTOCOMMIT")
        try:
            async with engine.connect() as conn:
                await conn.execute(sqlalchemy.text("DROP DATABASE test_edgy"))
        except Exception:
            pass
        async with engine.connect() as conn:
            await conn.execute(sqlalchemy.text("CREATE DATABASE test_edgy"))
        await engine.dispose()


@pytest.fixture(scope="function", autouse=True)
async def cleanup_db():
    for url in [DATABASE_ALTERNATIVE_URL, DATABASE_URL]:
        engine = create_async_engine(url, isolation_level="AUTOCOMMIT")
        try:
            async with engine.connect() as conn:
                await conn.execute(sqlalchemy.text("DROP DATABASE test_edgy"))
        except Exception:
            pass
        await engine.dispose()


@pytest.mark.parametrize("app_flag", ["explicit", "explicit_env"])
@pytest.mark.parametrize(
    "template_param",
    ["", " -t default", " -t plain", " -t url", " -t ./custom_multidb"],
    ids=["default_empty", "default", "plain", "url", "custom"],
)
async def test_migrate_upgrade_multidb(app_flag, template_param):
    os.chdir(base_path)
    assert not (base_path / "migrations").exists()
    app_param = "--app tests.cli.main_multidb " if app_flag == "explicit" else ""
    (o, e, ss) = await arun_cmd(
        "tests.cli.main_multidb",
        f"edgy {app_param}init{template_param}",
        with_app_environment=app_flag == "explicit_env",
        extra_env={"EDGY_SETTINGS_MODULE": "tests.settings.multidb.TestSettings"},
    )
    assert ss == 0

    (o, e, ss) = await arun_cmd(
        "tests.cli.main_multidb",
        f"edgy {app_param}makemigrations",
        with_app_environment=app_flag == "explicit_env",
        extra_env={"EDGY_SETTINGS_MODULE": "tests.settings.multidb.TestSettings"},
    )
    assert ss == 0
    assert b"No changes in schema detected" not in o

    (o, e, ss) = await arun_cmd(
        "tests.cli.main_multidb",
        f"edgy {app_param}migrate",
        with_app_environment=app_flag == "explicit_env",
        extra_env={"EDGY_SETTINGS_MODULE": "tests.settings.multidb.TestSettings"},
    )
    assert ss == 0

    (o, e, ss) = await arun_cmd(
        "tests.cli.main_multidb",
        f"hatch run python {__file__} test_migrate_upgrade_multidb",
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


@pytest.mark.parametrize("app_flag", ["explicit", "explicit_env"])
@pytest.mark.parametrize(
    "template_param",
    ["", " -t default", " -t plain", " -t url", " -t ./custom_multidb"],
    ids=["default_empty", "default", "plain", "url", "custom"],
)
async def test_different_directory(app_flag, template_param):
    os.chdir(base_path)
    assert not (base_path / "migrations2").exists()
    app_param = "--app tests.cli.main_multidb " if app_flag == "explicit" else ""
    (o, e, ss) = await arun_cmd(
        "tests.cli.main_multidb",
        f"edgy {app_param}init -d migrations2 {template_param}",
        with_app_environment=app_flag == "explicit_env",
        extra_env={"EDGY_SETTINGS_MODULE": "tests.settings.multidb.TestSettings"},
    )
    (o, e, ss) = await arun_cmd(
        "tests.cli.main_multidb",
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


@pytest.mark.parametrize(
    "env_extra",
    [
        {"EDGY_DATABASE": "another"},
        {"EDGY_DATABASE_URL": TEST_DATABASE, "EDGY_DATABASE": "another"},
        {"EDGY_DATABASE_URL": TEST_ALTERNATIVE_DATABASE, "EDGY_DATABASE": " "},
        {"EDGY_DATABASE_URL": TEST_ALTERNATIVE_DATABASE},
    ],
    ids=[
        "only_another",
        "only_another_and_custom_url",
        "only_main_and_custom_url",
        "retrieve_via_url",
    ],
)
@pytest.mark.parametrize(
    "template_param",
    ["", " -t default", " -t plain", " -t url", " -t ./custom_multidb"],
    ids=["default_empty", "default", "plain", "url", "custom"],
)
async def test_single_db(template_param, env_extra):
    app_flag = "explicit"
    os.chdir(base_path)
    assert not (base_path / "migrations").exists()
    app_param = "--app tests.cli.main_multidb " if app_flag == "explicit" else ""
    (o, e, ss) = await arun_cmd(
        "tests.cli.main_multidb",
        f"edgy {app_param}init {template_param}",
        with_app_environment=app_flag == "explicit_env",
        extra_env={"EDGY_SETTINGS_MODULE": "tests.settings.multidb.TestSettings", **env_extra},
    )

    assert ss == 0

    (o, e, ss) = await arun_cmd(
        "tests.cli.main_multidb",
        f"edgy {app_param}makemigrations",
        with_app_environment=app_flag == "explicit_env",
        extra_env={"EDGY_SETTINGS_MODULE": "tests.settings.multidb.TestSettings", **env_extra},
    )
    assert ss == 0
    assert b"No changes in schema detected" not in o

    (o, e, ss) = await arun_cmd(
        "tests.cli.main_multidb",
        f"edgy {app_param}migrate",
        with_app_environment=app_flag == "explicit_env",
        extra_env={"EDGY_SETTINGS_MODULE": "tests.settings.multidb.TestSettings", **env_extra},
    )
    assert ss == 0

    (o, e, ss) = await arun_cmd(
        "tests.cli.main_multidb",
        f"hatch run python {__file__} test_single_db",
        with_app_environment=False,
        extra_env={"EDGY_SETTINGS_MODULE": "tests.settings.multidb.TestSettings", **env_extra},
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


async def main():
    if sys.argv[1] == "test_single_db":
        from tests.cli import main_multidb as main

        if os.environ.get("EDGY_DATABASE_URL") and os.environ.get("EDGY_DATABASE") == "another":
            async with main.models:
                await main.Unrelated.query.using(database=None).create(name="foo")
                # should fail
                with pytest.raises(ProgrammingError):
                    await main.Unrelated.query.create(name="foo")
                # should fail
                with pytest.raises(ProgrammingError):
                    await main.User.query.create(name="edgy")
        elif os.environ.get("EDGY_DATABASE_URL") and os.environ.get("EDGY_DATABASE") == " ":
            async with main.models:
                # othewise content type crash
                main.models.content_type.database = main.models.extra["another"]
                await main.User.query.using(database="another").create(name="edgy")
                # should fail
                with pytest.raises(ProgrammingError):
                    await main.User.query.create(name="edgy2")
                # should fail
                with pytest.raises(ProgrammingError):
                    await main.Unrelated.query.create(name="foo")
        elif os.environ.get("EDGY_DATABASE_URL") or os.environ.get("EDGY_DATABASE") == "another":
            # should fail
            with pytest.raises(ProgrammingError):
                await main.User.query.create(name="edgy")
            # should fail
            with pytest.raises(ProgrammingError):
                await main.User.query.using(database="another").create(name="edgy")
            await main.Unrelated.query.create(name="foo")
    elif sys.argv[1] == "test_migrate_upgrade_multidb":
        from tests.cli import main_multidb as main

        async with main.models:
            user = await main.User.query.create(name="edgy")

            signal = await main.Signal.query.create(user=user, signal_type="foo")
            assert signal.user == user
            permission = await main.Permission.query.create(users=[user], name="view")
            assert await main.Permission.query.users("view").get() == user
            assert await main.Permission.query.permissions_of(user).get() == permission


if __name__ == "__main__":
    run(main())
