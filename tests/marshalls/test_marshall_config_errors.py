import sys

import pytest

import edgy
from edgy.core.marshalls import Marshall, fields
from edgy.core.marshalls.config import ConfigMarshall
from edgy.exceptions import MarshallFieldDefinitionError
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=edgy.Database(database, force_rollback=True))

pytestmark = pytest.mark.anyio


class User(edgy.Model):
    name: str = edgy.CharField(max_length=100, null=True)
    email: str = edgy.EmailField(max_length=100, null=True)
    language: str = edgy.CharField(max_length=200, null=True)
    description: str = edgy.TextField(max_length=5000, null=True)

    class Meta:
        registry = models


class Profile(edgy.Model):
    name: str = edgy.CharField(max_length=100)
    email: str = edgy.EmailField(max_length=100)

    class Meta:
        registry = models


def test_raises_error_on_missing_marshall_config():
    with pytest.raises(MarshallFieldDefinitionError) as raised:

        class UserMarshall(Marshall):
            details: fields.MarshallField = fields.MarshallMethodField(field_type=str)

    assert (
        raised.value.args[0]
        == "The 'marshall_config' was not found. Make sure it is declared and set."
    )


def test_raises_assertation_error_on_using_both_fields_and_exclude():
    with pytest.raises(AssertionError) as raised:

        class UserMarshall(Marshall):
            marshall_config = ConfigMarshall(model=User, fields=["email"], exclude=["language"])
            details: fields.MarshallField = fields.MarshallMethodField(field_type=str)

    assert raised.value.args[0] == "Use either 'fields' or 'exclude', not both."


def test_raises_assertation_error_on_missing_both_fields_and_exclude():
    with pytest.raises(AssertionError) as raised:

        class UserMarshall(Marshall):
            marshall_config = ConfigMarshall(model=User)
            details: fields.MarshallField = fields.MarshallMethodField(field_type=str)

    assert raised.value.args[0] == "Either 'fields' or 'exclude' must be declared."


def test_raises_error_on_missing_declared_function_on_method_field():
    with pytest.raises(MarshallFieldDefinitionError) as raised:

        class UserMarshall(Marshall):
            marshall_config = ConfigMarshall(model=User, fields=["email"])
            details: fields.MarshallField = fields.MarshallMethodField(field_type=str)

    assert (
        raised.value.args[0]
        == "Field 'details' declared but no 'get_details' found in 'UserMarshall'."
    )


def test_raises_error_on_incomplete_fields():
    class ProfileMarshall(Marshall):
        marshall_config = ConfigMarshall(model=Profile, fields=["email"])

    with pytest.raises(RuntimeError) as raised:
        ProfileMarshall(email="foo@example.com").instance  # noqa

    assert (
        raised.value.args[0]
        == "'ProfileMarshall' is an incomplete Marshall. For creating new instances, it lacks following fields: [name]."
    )


@pytest.mark.skipif(
    sys.version_info < (3, 12),
    reason=(
        "requires python 3.12 or higher to get this error. "
        "Otherwise it fails with a pydantic UserWarning because of incompatibilies "
        "with a non-classVar, non-typing_extensions TypedDict."
    ),
)
def test_raises_error_on_missing_classvar():
    with pytest.raises(MarshallFieldDefinitionError) as raised:

        class ProfileMarshall(Marshall):
            marshall_config: ConfigMarshall = ConfigMarshall(model=Profile, fields=["__all__"])

    assert (
        raised.value.args[0]
        == "'marshall_config' is part of the fields of 'ProfileMarshall'. Did you forgot to annotate with 'ClassVar'?"
    )
