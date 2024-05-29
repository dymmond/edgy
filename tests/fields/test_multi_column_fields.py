from typing import Any, Dict, Sequence

import pytest
import sqlalchemy

import edgy
from edgy.core.db.fields.base import BaseField
from edgy.core.db.fields.core import FieldFactory
from edgy.testclient import DatabaseTestClient as Database
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio
database = Database(DATABASE_URL)
models = edgy.Registry(database=database)


class MultiColumnFieldInner(BaseField):
    def get_columns(self, field_name: str) -> Sequence[sqlalchemy.Column]:
        return [
            sqlalchemy.Column(
                field_name,
                self.column_type,
                *self.constraints,
                primary_key=self.primary_key,
                nullable=self.null and not self.primary_key,
                index=self.index,
                unique=self.unique,
                default=self.default,
                comment=self.comment,
                server_default=self.server_default,
                server_onupdate=self.server_onupdate,
            ),
            sqlalchemy.Column(
                field_name + "_inner",
                self.column_type,
                *self.constraints,
                primary_key=self.primary_key,
                nullable=self.null and not self.primary_key,
                index=self.index,
                unique=self.unique,
                default=self.default,
                comment=self.comment,
                server_default=self.server_default,
                server_onupdate=self.server_onupdate,
            ),
        ]

    def clean(self, field_name: str, value: Any) -> Dict[str, Any]:
        """
        Runs the checks for the fields being validated.
        """
        return {field_name: value, field_name + "_inner": value}


class MultiColumnField(FieldFactory):
    _bases = (MultiColumnFieldInner,)
    _type = str

    @classmethod
    def get_column_type(cls, **kwargs: Any) -> Any:
        return sqlalchemy.Text(collation=kwargs.get("collation", None))


class MyModel(edgy.Model):
    multi = MultiColumnField()

    class Meta:
        registry = models


@pytest.fixture()
async def create_test_database():
    await models.create_all()
    yield
    await models.drop_all()


@pytest.fixture()
async def rollback_connections(create_test_database):
    with database.force_rollback():
        async with database:
            yield


async def test_create_and_assign(rollback_connections):
    obj = await MyModel.query.create(multi="edgy", multi_inner="edgytoo")
    assert obj.multi == "edgy"
    assert hasattr(MyModel.table.columns, "multi_inner")
    obj.multi = "test"
    await obj.save()
    assert await MyModel.query.filter(MyModel.table.columns.multi_inner == "test").exists()
