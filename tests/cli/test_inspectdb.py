from io import StringIO

import pytest
from tests.cli.utils import run_cmd
from tests.settings import DATABASE_URL

import edgy
from edgy.core.db.datastructures import Index

pytestmark = pytest.mark.anyio

database = edgy.Database(DATABASE_URL)
models = edgy.Registry(database=database)


class User(edgy.Model):
    name = edgy.CharField(max_length=255, index=True)
    title = edgy.CharField(max_length=255, null=True)

    class Meta:
        registry = models
        indexes = [Index(fields=["name", "title"], name="idx_name_title")]


class HubUser(edgy.Model):
    name = edgy.CharField(max_length=255)
    title = edgy.CharField(max_length=255, null=True)
    description = edgy.CharField(max_length=255, null=True)

    class Meta:
        registry = models
        indexes = [
            Index(fields=["name", "title"], name="idx_title_name"),
            Index(fields=["name", "description"], name="idx_name_description"),
        ]


class Transaction(edgy.Model):
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


@pytest.fixture(autouse=True)
async def rollback_transactions():
    with database.force_rollback():
        async with database:
            yield


async def test_inspect_db():
    out = StringIO()

    (out, error, ss) = run_cmd("tests.cli.main:app", f"edgy inspectdb --db_url={DATABASE_URL}")

    out = out.decode("utf8")

    assert "class Users" in out
    assert "class Hubusers" in out
    assert "class Transactions" in out
    assert (
        "unique_together = [UniqueConstraint(fields=['amount', 'total'], suffix='uq', name='uq_amount_total', max_name_length=30)]"
        in out
    )
    assert (
        "indexes = [Index(suffix='idx', max_name_length=30, name='idx_name_description', fields=['name', 'description']), Index(suffix='idx', max_name_length=30, name='idx_title_name', fields=['name', 'title'])]"
        in out
    )
    assert ss == 0
