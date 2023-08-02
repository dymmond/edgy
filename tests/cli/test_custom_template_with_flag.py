import os
import shutil

import pytest
from esmerald import Esmerald
from tests.cli.utils import run_cmd

app = Esmerald(routes=[])


@pytest.fixture(scope="module")
def create_folders():
    os.chdir(os.path.split(os.path.abspath(__file__))[0])
    try:
        os.remove("app.db")
    except OSError:
        pass
    try:
        shutil.rmtree("migrations")
    except OSError:
        pass
    try:
        shutil.rmtree("temp_folder")
    except OSError:
        pass

    yield

    try:
        os.remove("app.db")
    except OSError:
        pass
    try:
        shutil.rmtree("migrations")
    except OSError:
        pass
    try:
        shutil.rmtree("temp_folder")
    except OSError:
        pass


def test_alembic_version():
    from edgy.cli import alembic_version

    assert len(alembic_version) == 3

    for v in alembic_version:
        assert isinstance(v, int)


def test_migrate_upgrade_with_app_flag(create_folders):
    (o, e, ss) = run_cmd(
        "tests.cli.main:app", "edgy --app tests.cli.main:app init -t ./custom", is_app=False
    )
    assert ss == 0

    (o, e, ss) = run_cmd(
        "tests.cli.main:app", "edgy --app tests.cli.main:app makemigrations", is_app=False
    )
    assert ss == 0

    (o, e, ss) = run_cmd(
        "tests.cli.main:app", "edgy --app tests.cli.main:app migrate", is_app=False
    )
    assert ss == 0

    with open("migrations/README") as f:
        assert f.readline().strip() == "Custom template"
    with open("migrations/alembic.ini") as f:
        assert f.readline().strip() == "# A generic, single database configuration"
    with open("migrations/env.py") as f:
        assert f.readline().strip() == "# Custom env template"
    with open("migrations/script.py.mako") as f:
        assert f.readline().strip() == "# Custom mako template"
