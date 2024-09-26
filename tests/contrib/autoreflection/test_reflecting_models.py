import pytest

import edgy
from edgy.contrib.autoreflection import AutoReflectModel
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio
database = DatabaseTestClient(DATABASE_URL, use_existing=False)
source = edgy.Registry(database=database)


class Foo(edgy.Model):
    a = edgy.CharField(max_length=40)
    b = edgy.CharField(max_length=40, column_name="c")

    class Meta:
        registry = source


class Bar(edgy.Model):
    a = edgy.CharField(max_length=40)

    class Meta:
        registry = source


class NotFoo(edgy.Model):
    a = edgy.CharField(max_length=40)

    class Meta:
        registry = source


@pytest.fixture(autouse=True, scope="function")
async def create_test_database():
    async with database:
        await source.create_all()
        yield
        if not database.drop:
            await source.drop_all()


async def test_basic_reflection():
    reflected = edgy.Registry(DATABASE_URL)

    class AutoAll(AutoReflectModel):
        class Meta:
            registry = reflected

    class AutoNever(AutoReflectModel):
        non_matching = edgy.CharField(max_length=40)

        class Meta:
            registry = reflected
            template = r"AutoNever"

    class AutoNever2(AutoReflectModel):
        id = edgy.CharField(max_length=40, primary_key=True)

        class Meta:
            registry = reflected
            template = r"AutoNever2"

    class AutoNever3(AutoReflectModel):
        class Meta:
            registry = reflected
            template = r"AutoNever3"
            exclude_pattern = r".*"

    class AutoFoo(AutoReflectModel):
        class Meta:
            registry = reflected
            include_pattern = r"^foos$"

    class AutoBar(AutoReflectModel):
        class Meta:
            registry = reflected
            include_pattern = r"^bars"
            template = r"{tablename}_{tablename}"

    assert AutoBar.meta.template

    async with reflected:
        assert (
            sum(
                1 for model in reflected.reflected.values() if model.__name__.startswith("AutoAll")
            )
            == 3
        )
        assert "bars_bars" in reflected.reflected
        assert "AutoNever" not in reflected.reflected
        assert "AutoNever2" not in reflected.reflected
        assert "AutoNever3" not in reflected.reflected

        assert (
            sum(
                1 for model in reflected.reflected.values() if model.__name__.startswith("AutoFoo")
            )
            == 1
        )
