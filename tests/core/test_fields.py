import pytest

from edgy.core.db.base import BaseField
from edgy.core.db.fields import StringField
from edgy.exceptions import FieldDefinitionError


def test_can_create_string_field():
    string = StringField(min_length=5, max_length=10, null=True)

    assert isinstance(string, BaseField)
    assert string.min_length == 5
    assert string.max_length == 10
    assert string.null is True


def test_raises_field_definition_error_on_string_creation():
    with pytest.raises(FieldDefinitionError):
        StringField(min_length=10, null=False)
