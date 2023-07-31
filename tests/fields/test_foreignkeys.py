import pytest

import edgy
from edgy import ForeignKey, Model, OneToOne, OneToOneField
from edgy.exceptions import FieldDefinitionError


class MyModel(Model):
    """"""


@pytest.mark.parametrize("model", [ForeignKey, OneToOne, OneToOneField])
def test_can_create_foreign_key(model):
    fk = model(to=MyModel)

    assert fk is not None
    assert fk.to == MyModel


def test_raise_error_on_delete_fk():
    with pytest.raises(FieldDefinitionError):
        ForeignKey(to=MyModel, on_delete=None)


def test_raise_error_on_delete_null():
    with pytest.raises(FieldDefinitionError):
        ForeignKey(to=MyModel, on_delete=edgy.SET_NULL)


def test_raise_error_on_update_null():
    with pytest.raises(FieldDefinitionError):
        ForeignKey(to=MyModel, on_update=edgy.SET_NULL)
