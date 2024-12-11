import contextlib
import os
import shutil
from pathlib import Path

import pytest
import sqlalchemy
from esmerald import Esmerald
from sqlalchemy.ext.asyncio import create_async_engine

from tests.cli.utils import arun_cmd
from tests.settings import (
    DATABASE_ALTERNATIVE_URL,
    DATABASE_URL,
    TEST_ALTERNATIVE_DATABASE,
)

pytestmark = pytest.mark.anyio

app = Esmerald(routes=[])

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


@pytest.mark.parametrize("app_flag", ["explicit", "explicit_env"])
@pytest.mark.parametrize(
    "template_param",
    ["", " -t default", " -t plain", " -t url", " -t ./custom_multidb"],
    ids=["default_empty", "default", "plain", "url", "custom"],
)
async def test_migrate_upgrade(app_flag, template_param):
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

    (o, e, ss) = await arun_cmd(
        "tests.cli.main_multidb",
        f"edgy {app_param}migrate",
        with_app_environment=app_flag == "explicit_env",
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


@pytest.mark.parametrize("app_flag", ["explicit", "explicit_env"])
@pytest.mark.parametrize(
    "env_extra",
    [
        {"EDGY_DATABASE": ""},
        {"EDGY_DATABASE_URL": TEST_ALTERNATIVE_DATABASE, "EDGY_DATABASE": ""},
        {"EDGY_DATABASE_URL": TEST_ALTERNATIVE_DATABASE},
    ],
)
@pytest.mark.parametrize(
    "template_param",
    ["", " -t default", " -t plain", " -t url", " -t ./custom_multidb"],
    ids=["default_empty", "default", "plain", "url", "custom"],
)
async def test_single_db(app_flag, template_param, env_extra):
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

    (o, e, ss) = await arun_cmd(
        "tests.cli.main_multidb",
        f"edgy {app_param}migrate",
        with_app_environment=app_flag == "explicit_env",
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
