from enum import Enum

import pytest

import edgy
from edgy import Registry
from edgy.exceptions import FieldDefinitionError
from edgy.testclient import DatabaseTestClient as Database
from tests.settings import DATABASE_URL

database = Database(url=DATABASE_URL)
models = Registry(database=database)
nother = Registry(database=database)

pytestmark = pytest.mark.anyio


class StatusEnum(Enum):
    DRAFT = "Draft"
    RELEASED = "Released"


@pytest.mark.parametrize(
    "field,max_length,max_digits,decimal_places",
    [
        (edgy.BooleanField, None, None, None),
        (edgy.CharField, 255, None, None),
        (edgy.UUIDField, None, None, None),
        (edgy.TextField, None, None, None),
        (edgy.DateField, None, None, None),
        (edgy.DateTimeField, None, None, None),
        (edgy.FloatField, None, None, None),
        (edgy.DecimalField, None, 5, 2),
        (edgy.TimeField, None, None, None),
        (edgy.ChoiceField, None, None, None),
    ],
    ids=[
        "BooleanField",
        "CharField",
        "UUIDField",
        "TextField",
        "DateField",
        "DateTimeField",
        "FloatField",
        "DecimalField",
        "TimeField",
        "ChoiceField",
    ],
)
async def test_model_custom_primary_key_raised_error_without_default(field, max_length, max_digits, decimal_places):
    with pytest.raises(FieldDefinitionError) as raised:
        kwargs = {
            "max_length": max_length,
            "max_digits": max_digits,
            "decimal_places": decimal_places,
            "choices": StatusEnum,
        }

        class Profile(edgy.Model):
            id = field(primary_key=True, **kwargs)
            language = edgy.CharField(max_length=200, null=True)
            age = edgy.IntegerField()

            class Meta:
                registry = models

    assert (
        raised.value.args[0]
        == "Primary keys other then IntegerField and BigIntegerField, must provide a default or a server_default."
    )
