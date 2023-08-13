import os

import pytest
from esmerald import Esmerald
from tests.settings import DATABASE_URL

import edgy
from edgy import EdgyExtra
from edgy.testclient import DatabaseTestClient

pytestmark = pytest.mark.anyio
database = DatabaseTestClient(DATABASE_URL, drop_database=True)
models = edgy.Registry(database=database)

basedir = os.path.abspath(os.path.dirname(__file__))


class AppUser(edgy.Model):
    name = edgy.CharField(max_length=255)

    class Meta:
        registry = models


app = Esmerald(routes=[])
EdgyExtra(app, registry=models)
