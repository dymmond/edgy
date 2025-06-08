from inspect import isawaitable

import pytest

import edgy
from edgy.core.db.datastructures import Index
from edgy.testing import DatabaseTestClient
from tests.cli.utils import arun_cmd, run_cmd
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio

models = edgy.Registry(
    database=DatabaseTestClient(
        DATABASE_URL, force_rollback=False, drop_database=False, test_prefix=""
    )
)


class User(edgy.StrictModel):
    name = edgy.CharField(max_length=255, index=True)
    title = edgy.CharField(max_length=255, null=True)

    class Meta:
        registry = models
        indexes = [Index(fields=["name", "title"], name="idx_name_title")]


class HubUser(edgy.StrictModel):
    name = edgy.CharField(max_length=255)
    title = edgy.CharField(max_length=255, null=True)
    description = edgy.CharField(max_length=255, null=True)

    class Meta:
        registry = models
        indexes = [
            Index(fields=["name", "title"], name="idx_title_name"),
            Index(fields=["name", "description"], name="idx_name_description"),
        ]


class Transaction(edgy.StrictModel):
    amount = edgy.DecimalField(max_digits=9, decimal_places=2)
    total = edgy.FloatField()

    class Meta:
        registry = models
        unique_together = [edgy.UniqueConstraint(fields=["amount", "total"])]


@pytest.fixture(autouse=True, scope="module")
async def create_test_database():
    await models.create_all()
    yield
    await models.drop_all()


async def test_inspect_db():
    (out, error, ss) = run_cmd("tests.cli.main", f"edgy inspectdb --database={DATABASE_URL}")

    out = out.decode("utf8")

    assert "class Users" in out
    assert "class Hubusers" in out
    assert "class Transactions" in out
    assert ss == 0


@pytest.mark.parametrize("cmd", [run_cmd, arun_cmd], ids=["sync", "async"])
async def test_inspect_db_with_schema(cmd):
    result = cmd("tests.cli.main", f"edgy inspectdb --database={DATABASE_URL} --schema='public'")
    if isawaitable(result):
        result = await result
    (out, error, ss) = result

    out = out.decode("utf8")
    assert "class Users" in out
    assert "class Hubusers" in out
    assert "class Transactions" in out
    assert "registry = edgy.Registry(database=database, schema='public')" in out
    assert ss == 0
