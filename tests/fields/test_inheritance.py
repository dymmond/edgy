from typing import Type

import pytest

from edgy.core.db.fields import (
    BigIntegerField,
    BinaryField,
    CharField,
    DateField,
    DateTimeField,
    DecimalField,
    ExcludeField,
    FloatField,
    IntegerField,
    JSONField,
    SmallIntegerField,
    TextField,
    TimeField,
    UUIDField,
)
from edgy.core.db.models import Model


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


def test_overwriting_fields_with_fields():
    class AbstractModel(Model):
        first_name: str = CharField(max_length=255)
        last_name: str = CharField(max_length=255)

        class Meta:
            abstract = True

    class ConcreteModel1(AbstractModel):
        last_name: int = IntegerField()

    class ConcreteModel2(ConcreteModel1):
        first_name: str = CharField(max_length=50)

    assert ConcreteModel1.meta.fields_mapping["first_name"].max_length == 255
    assert isinstance(ConcreteModel1.meta.fields_mapping["last_name"], IntegerField)
    assert ConcreteModel2.meta.fields_mapping["first_name"].max_length == 50


def test_deleting_fields():
    class AbstractModel(Model):
        first_name: str = CharField(max_length=255)
        last_name: str = CharField(max_length=255)

        class Meta:
            abstract = True

    class ConcreteModel1(AbstractModel):
        last_name: Type[None] = ExcludeField()

    class ConcreteModel2(ConcreteModel1):
        first_name: Type[None] = ExcludeField()

    assert ConcreteModel1.meta.fields_mapping["first_name"].max_length == 255
    model1 = ConcreteModel1(first_name="edgy", last_name="edgy")
    model2 = ConcreteModel2(first_name="edgy", last_name="edgy")
    assert model1.first_name == "edgy"
    with pytest.raises(AttributeError):
        _ = model1.last_name
    with pytest.raises(AttributeError):
        model1.last_name = "edgy"

    with pytest.raises(AttributeError):
        _ = model2.first_name
    with pytest.raises(AttributeError):
        model2.first_name = "edgy"
    with pytest.raises(AttributeError):
        _ = model2.last_name
    with pytest.raises(AttributeError):
        model2.last_name = "edgy"


def test_mixins_non_inherited():
    class Mixin:
        field = CharField(max_length=255, inherit=False)

    class Mixin2:
        field = CharField(max_length=255, inherit=False)

    class AbstractModel(Mixin, Model):
        pass

        class Meta:
            abstract = True

    class ConcreteModel1(AbstractModel):
        pass
    assert not ConcreteModel1.meta.abstract
    assert "field" in ConcreteModel1.meta.fields_mapping

    class ConcreteModel2(ConcreteModel1):
        field3 = CharField(max_length=255, inherit=False)
    assert not ConcreteModel2.meta.abstract
    assert "field" not in ConcreteModel2.meta.fields_mapping

    class ConcreteModel3(Mixin2, ConcreteModel1):
        pass

    assert "field" in ConcreteModel3.meta.fields_mapping



def test_mixins_mixed_inherited():
    class Mixin2:
        field = CharField(max_length=250, inherit=True)

    class Mixin(Mixin2):
        field = CharField(max_length=255, inherit=False)

    class AbstractModel(Mixin, Model):
        pass

        class Meta:
            abstract = True

    class ConcreteModel1(AbstractModel):
        pass
    assert not ConcreteModel1.meta.abstract
    assert ConcreteModel1.meta.fields_mapping["field"].max_length == 255

    class ConcreteModel2(ConcreteModel1):
        pass
    assert not ConcreteModel2.meta.abstract
    assert ConcreteModel2.meta.fields_mapping["field"].max_length == 250
