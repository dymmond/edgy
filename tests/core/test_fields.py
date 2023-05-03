import datetime

import pytest

from edgy.core.db.base import BaseField
from edgy.core.db.fields import (
    BooleanField,
    DateField,
    DateTimeField,
    FloatField,
    StringField,
    TextField,
    TimeField,
)
from edgy.exceptions import FieldDefinitionError


def test_column_type():
    assert StringField.get_column_type() == str
    assert TextField.get_column_type() == str
    assert FloatField.get_column_type() == float
    assert BooleanField.get_column_type() == bool
    assert DateTimeField.get_column_type() == datetime.datetime
    assert DateField.get_column_type() == datetime.date
    assert TimeField.get_column_type() == datetime.time


def test_can_create_string_field():
    field = StringField(min_length=5, max_length=10, null=True)

    assert isinstance(field, BaseField)
    assert field.min_length == 5
    assert field.max_length == 10
    assert field.null is True


def test_raises_field_definition_error_on_string_creation():
    with pytest.raises(FieldDefinitionError):
        StringField(min_length=10, null=False)


def test_can_create_text_field():
    field = TextField(min_length=5, null=True)

    assert isinstance(field, BaseField)
    assert field.min_length == 5
    assert field.max_length is None
    assert field.null is True


def test_can_create_float_field():
    field = FloatField(minimum=5, maximum=10, null=True)

    assert isinstance(field, BaseField)
    assert field.minimum == 5
    assert field.maximum == 10
    assert field.null is True


def test_can_create_boolean_field():
    field = BooleanField(default=False)

    assert isinstance(field, BaseField)
    assert field.default is False

    field = BooleanField(default=True)
    assert field.default is True

    field = BooleanField()
    assert field.default is False


def test_can_create_datetime_field():
    field = DateTimeField(auto_now=True)

    assert isinstance(field, BaseField)
    assert field.default == datetime.datetime.now
    assert field.read_only is True


def test_raises_field_definition_error_on_datetime_creation():
    with pytest.raises(FieldDefinitionError):
        DateTimeField(auto_now=True, auto_now_add=True)


def test_can_create_date_field():
    field = DateField(auto_now=True)

    assert isinstance(field, BaseField)
    assert field.default == datetime.datetime.today
    assert field.read_only is True


def test_raises_field_definition_error_on_date_creation():
    with pytest.raises(FieldDefinitionError):
        DateTimeField(auto_now=True, auto_now_add=True)


def test_can_create_time_field():
    field = TimeField(auto_now=True)

    assert isinstance(field, BaseField)
    assert field.read_only is False
