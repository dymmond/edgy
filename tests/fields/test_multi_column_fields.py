from collections.abc import Sequence
from typing import Any

import pytest
import sqlalchemy

import edgy
from edgy.core.db.fields.base import BaseField
from edgy.core.db.fields.core import FieldFactory
from edgy.core.db.fields.types import ColumnDefinitionModel
from edgy.core.db.querysets.clauses import and_
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio
database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=database)


class MultiColumnFieldInner(BaseField):
    def operator_to_clause(
        self, field_name: str, operator: str, table: sqlalchemy.Table, value: Any
    ) -> Any:
        # after clean
        return and_(
            super().operator_to_clause(field_name, operator, table, value["normal"]),
            super().operator_to_clause(field_name + "_inner", operator, table, value["inner"]),
        )

    def get_columns(self, field_name: str) -> Sequence[sqlalchemy.Column]:
        model = ColumnDefinitionModel.model_validate(self, from_attributes=True)
        return [
            sqlalchemy.Column(
                field_name,
                model.column_type,
                *model.constraints,
                nullable=self.get_columns_nullable(),
                **model.model_dump(by_alias=True, exclude_none=True),
            ),
            sqlalchemy.Column(
                field_name + "_inner",
                model.column_type,
                *model.constraints,
                nullable=self.get_columns_nullable(),
                **model.model_dump(by_alias=True, exclude_none=True),
            ),
        ]

    def _clean(self, field_name: str, value: Any) -> dict[str, Any]:
        if isinstance(value, str):
            return {field_name: value, field_name + "_inner": value}
        return {field_name: value["normal"], field_name + "_inner": value["inner"]}

    def clean(self, field_name: str, value: Any, for_query: bool = False) -> dict[str, Any]:
        if for_query:
            # we need to wrap for operators
            result = self._clean("normal", value)
            result["inner"] = result.pop("normal_inner")
            return {field_name: result}
        else:
            return self._clean(field_name, value)

    def modify_input(self, field_name: str, kwargs: Any) -> None:
        if field_name not in kwargs and field_name + "_inner" not in kwargs:
            return
        normal = kwargs.pop(field_name, None)
        if isinstance(normal, dict):
            kwargs[field_name] = normal
        else:
            kwargs[field_name] = {
                "normal": normal,
                "inner": kwargs.pop(field_name + "_inner", normal),
            }

    def to_model(self, field_name: str, value: Any) -> dict[str, Any]:
        if isinstance(value, str):
            return {field_name: {"normal": value, "inner": value}}
        return {field_name: value}


class MultiColumnField(FieldFactory):
    field_bases = (MultiColumnFieldInner,)
    field_type = Any

    @classmethod
    def get_column_type(cls, kwargs: dict[str, Any]) -> Any:
        return sqlalchemy.Text(collation=kwargs.get("collation"))


class MyModel(edgy.StrictModel):
    multi = MultiColumnField()

    class Meta:
        registry = models


@pytest.fixture()
async def create_test_database():
    async with database:
        await models.create_all()
        yield
        if not database.drop:
            await models.drop_all()


def test_basic_model():
    obj = MyModel(multi="edgy")
    assert obj.multi["normal"] == "edgy"
    assert obj.multi["inner"] == "edgy"


async def test_create_and_assign(create_test_database):
    obj = await MyModel.query.create(multi="edgy", multi_inner="edgytoo")
    assert obj.multi["normal"] == "edgy"
    assert obj.multi["inner"] == "edgytoo"
    assert hasattr(MyModel.table.columns, "multi_inner")
    assert await MyModel.query.filter(multi__exact={"normal": "edgy", "inner": "edgytoo"}).exists()
    assert await MyModel.query.filter(multi__startswith="edgy").exists()
    obj.multi = "test"
    assert obj.multi["normal"] == "test"
    assert obj.multi["inner"] == "test"
    await obj.save()
    assert await MyModel.query.filter(MyModel.table.columns.multi_inner == "test").exists()
    assert await MyModel.query.filter(multi="test").exists()
    assert obj.multi["inner"] == "test"

    obj.multi = {"normal": "edgy", "inner": "foo"}
    await obj.save()
    assert await MyModel.query.filter(MyModel.table.columns.multi_inner == "foo").exists()
    assert obj.multi["normal"] == "edgy"


async def test_indb(create_test_database):
    obj = await MyModel.query.create(multi="edgy", multi_inner="edgytoo")
    assert obj.multi["normal"] == "edgy"
    assert obj.multi["inner"] == "edgytoo"

    await MyModel.query.update(
        multi={
            "normal": MyModel.table.c.multi + "foo",
            "inner": MyModel.table.c.multi_inner + "foo",
        }
    )
    await obj.load()
    assert obj.multi["normal"] == "edgyfoo"
    assert obj.multi["inner"] == "edgytoofoo"
