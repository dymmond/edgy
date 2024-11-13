import asyncio
import contextlib
import os
import shutil

import pytest
import sqlalchemy
from esmerald import Esmerald
from sqlalchemy.ext.asyncio import create_async_engine

from tests.cli.utils import run_cmd
from tests.settings import DATABASE_URL

app = Esmerald(routes=[])


@pytest.fixture(scope="module")
def create_folders():
    os.chdir(os.path.split(os.path.abspath(__file__))[0])
    with contextlib.suppress(OSError):
        os.remove("app.db")
    with contextlib.suppress(OSError):
        shutil.rmtree("migrations")
    with contextlib.suppress(OSError):
        shutil.rmtree("temp_folder")

    yield

    with contextlib.suppress(OSError):
        os.remove("app.db")
    with contextlib.suppress(OSError):
        shutil.rmtree("migrations")
    with contextlib.suppress(OSError):
        shutil.rmtree("temp_folder")


def test_alembic_version():
    from edgy.cli import alembic_version

    assert len(alembic_version) == 3

    for v in alembic_version:
        assert isinstance(v, int)


async def cleanup_prepare_db():
    engine = create_async_engine(DATABASE_URL, isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as conn:
            await conn.execute(sqlalchemy.text("DROP DATABASE test_edgy"))
    except Exception:
        pass
    async with engine.connect() as conn:
        await conn.execute(sqlalchemy.text("CREATE DATABASE test_edgy"))


def test_migrate_upgrade(create_folders):
    asyncio.run(cleanup_prepare_db())
    (o, e, ss) = run_cmd("tests.cli.main", "edgy init")
    assert ss == 0

    (o, e, ss) = run_cmd("tests.cli.main", "edgy makemigrations")
    assert ss == 0

    (o, e, ss) = run_cmd("tests.cli.main", "edgy migrate")
    assert ss == 0
