import pytest

from edgy.core.db.fields import (
    BigIntegerField,
    BinaryField,
    CharField,
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


@pytest.mark.parametrize(
    "field,_class",
    [
        (CharField(max_length=255, null=True), CharField),
        (TextField(null=True), TextField),
        (FloatField(null=True), FloatField),
        (DateTimeField(null=True), DateTimeField),
        (DateField(null=True), DateField),
        (TimeField(null=True), TimeField),
        (JSONField(null=True), JSONField),
        (BinaryField(max_length=255, null=True), BinaryField),
        (IntegerField(null=True), IntegerField),
        (BigIntegerField(null=True), BigIntegerField),
        (SmallIntegerField(null=True), SmallIntegerField),
        (DecimalField(max_digits=20, decimal_places=2, null=True), DecimalField),
        (UUIDField(null=True), UUIDField),
    ],
)
def test_isinstance_issubclass(field, _class):
    assert isinstance(field, _class)
    assert issubclass(field.__class__, _class)
    assert issubclass(_class, _class)
