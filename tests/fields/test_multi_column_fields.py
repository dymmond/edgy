from typing import Any, Dict, Sequence

import pytest
import sqlalchemy

import edgy
from edgy.core.db.fields.base import BaseField
from edgy.core.db.fields.core import FieldFactory
from edgy.core.db.fields.types import ColumnDefinitionModel
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio
database = DatabaseTestClient(DATABASE_URL, test_prefix="")
models = edgy.Registry(database=database)


class MultiColumnFieldInner(BaseField):
    def get_columns(self, field_name: str) -> Sequence[sqlalchemy.Column]:
        model = ColumnDefinitionModel.model_validate(self, from_attributes=True)
        return [
            sqlalchemy.Column(
                field_name,
                model.column_type,
                *model.constraints,
                **model.model_dump(by_alias=True, exclude_none=True),
            ),
            sqlalchemy.Column(
                field_name + "_inner",
                model.column_type,
                *model.constraints,
                **model.model_dump(by_alias=True, exclude_none=True),
            ),
        ]

    def clean(self, field_name: str, value: Any, for_query: bool = False) -> Dict[str, Any]:
        """
        Runs the checks for the fields being validated.
        """
        if isinstance(value, str):
            return {field_name: value, field_name + "_inner": value}
        return {field_name: value["normal"], field_name + "_inner": value["inner"]}

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

    def to_model(self, field_name: str, value: Any, phase: str = "") -> Dict[str, Any]:
        if isinstance(value, str):
            return {field_name: {"normal": value, "inner": value}}
        return {field_name: value}


class MultiColumnField(FieldFactory):
    field_bases = (MultiColumnFieldInner,)
    field_type = Any

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


def test_basic_mdoel():
    obj = MyModel(multi="edgy")
    assert obj.multi["normal"] == "edgy"
    assert obj.multi["inner"] == "edgy"


async def test_create_and_assign(rollback_connections):
    obj = await MyModel.query.create(multi="edgy", multi_inner="edgytoo")
    assert obj.multi["normal"] == "edgy"
    assert obj.multi["inner"] == "edgytoo"
    assert hasattr(MyModel.table.columns, "multi_inner")
    obj.multi = "test"
    assert obj.multi["normal"] == "test"
    assert obj.multi["inner"] == "test"
    await obj.save()
    assert await MyModel.query.filter(MyModel.table.columns.multi_inner == "test").exists()
    assert obj.multi["inner"] == "test"

    obj.multi = {"normal": "edgy", "inner": "foo"}
    await obj.save()
    assert await MyModel.query.filter(MyModel.table.columns.multi_inner == "foo").exists()
    assert obj.multi["normal"] == "edgy"
