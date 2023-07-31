import datetime
import enum
import uuid

import pytest
import sqlalchemy

from edgy.core.db.base import BaseField
from edgy.core.db.fields import (
    BigIntegerField,
    BinaryField,
    BooleanField,
    CharField,
    ChoiceField,
    DateField,
    DateTimeField,
    DecimalField,
    FloatField,
    IntegerField,
    JSONField,
    SmallIntegerField,
    TextField,
    TimeField,
    UUIDField,
)
from edgy.exceptions import FieldDefinitionError


def test_column_type():
    assert isinstance(CharField.get_column_type(), sqlalchemy.String)
    assert isinstance(TextField.get_column_type(), sqlalchemy.String)
    assert isinstance(FloatField.get_column_type(), sqlalchemy.Float)
    assert isinstance(BooleanField.get_column_type(), sqlalchemy.Boolean)
    assert isinstance(DateTimeField.get_column_type(), sqlalchemy.DateTime)
    assert isinstance(DateField.get_column_type(), sqlalchemy.Date)
    assert isinstance(TimeField.get_column_type(), sqlalchemy.Time)
    assert isinstance(JSONField.get_column_type(), sqlalchemy.JSON)
    assert isinstance(BinaryField.get_column_type(), sqlalchemy.JSON)
    assert isinstance(IntegerField.get_column_type(), sqlalchemy.Integer)
    assert isinstance(BigIntegerField.get_column_type(), sqlalchemy.BigInteger)
    assert isinstance(SmallIntegerField.get_column_type(), sqlalchemy.SmallInteger)
    assert isinstance(DecimalField.get_column_type(), sqlalchemy.Numeric)
    assert isinstance(UUIDField.get_column_type(), sqlalchemy.UUID)
    assert isinstance(ChoiceField.get_column_type(), sqlalchemy.Enum)


def test_can_create_string_field():
    field = CharField(min_length=5, max_length=10, null=True)

    assert isinstance(field, BaseField)
    assert field.min_length == 5
    assert field.max_length == 10
    assert field.null is True


def test_raises_field_definition_error_on_string_creation():
    with pytest.raises(FieldDefinitionError):
        CharField(min_length=10, null=False)


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


def test_can_create_json_field():
    field = JSONField(default={"json": "json"})

    assert isinstance(field, BaseField)
    assert field.default == {"json": "json"}


def test_can_create_binary_field():
    field = BinaryField(max_length=25)

    assert isinstance(field, BaseField)
    assert field.default is None


def test_raises_field_definition_error_on_binary_creation():
    with pytest.raises(FieldDefinitionError):
        BinaryField(max_length=0)


@pytest.mark.parametrize("klass", [FloatField, IntegerField, BigIntegerField, SmallIntegerField])
def test_can_create_integer_field(klass):
    field = klass(minimum=1, maximum=10)

    assert isinstance(field, BaseField)
    assert field.default is None


@pytest.mark.parametrize("klass", [FloatField, IntegerField, BigIntegerField, SmallIntegerField])
def test_raises_field_definition_error_in_numbers(klass):
    with pytest.raises(FieldDefinitionError):
        klass(minimum=20, maximum=10)

    with pytest.raises(FieldDefinitionError):
        klass(exclusive_minimum=20, exclusive_maximum=10)


def test_can_create_decimal_field():
    field = DecimalField(max_digits=2, decimal_places=2)

    assert isinstance(field, BaseField)
    assert field.default is None


def test_raises_field_definition_error_in_decimal():
    with pytest.raises(FieldDefinitionError):
        DecimalField(minimum=20, maximum=10)

    with pytest.raises(FieldDefinitionError):
        DecimalField(exclusive_minimum=20, exclusive_maximum=10)


def test_can_create_uuid_field():
    field = UUIDField(default=uuid.uuid4)

    assert isinstance(field, BaseField)
    assert field.default == uuid.uuid4


def test_can_choice_field():
    class StatusChoice(str, enum.Enum):
        ACTIVE = "active"
        INACTIVE = "inactive"

    field = ChoiceField(choices=StatusChoice)

    assert isinstance(field, BaseField)
    assert len(field.choices) == 2
