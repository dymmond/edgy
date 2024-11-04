import os

import pytest
from esmerald import Esmerald

import edgy
from edgy import Migrate
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio
database = DatabaseTestClient(DATABASE_URL, drop_database=True, test_prefix="test_")
models = edgy.Registry(database=database)

basedir = os.path.abspath(os.path.dirname(__file__))


class AppUser(edgy.StrictModel):
    name = edgy.CharField(max_length=255)

    class Meta:
        registry = models


app = Esmerald(routes=[])
Migrate(app, registry=models)
