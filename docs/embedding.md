# Embedding

There are two ways of embedding models

## Embeddable

Edgy models are capable of being used as an embeddable. This means just using a model like a field works
and *automagically* fields are copied with the prefix of the attribute name used plus an `_`.

Fields with `inherit=False` are not pulled in to prevent PKField or autoinjected id fields to be pulled in.


``` python
from typing import ClassVar
import edgy


class InheritableModel(edgy.Model):
    first_name: str = edgy.CharField(max_length=255)
    last_name: str = edgy.CharField(max_length=255)

    class Meta:
        abstract = True

class NonInheritableModel(edgy.Model):
    age: int = edgy.IntegerField()
    class Meta:
        abstract = True
        inherit = False



class MyModel1(edgy.Model):
    model1: ClassVar[InheritableModel] = InheritableModel
    # ClassVar is optional
    model2 = NonInheritableModel

class MyModel2(MyModel1):
    pass
    # NonInheritableModel is gone
```


## Explicit Control

You can also pass models as CompositeField `inner_fields` argument.
This is internally done by the first way

``` python
from typing import ClassVar
import edgy


class InheritableModel(edgy.Model):
    first_name: str = edgy.CharField(max_length=255)
    last_name: str = edgy.CharField(max_length=255)

    class Meta:
        abstract = True

class NonInheritableModel(edgy.Model):
    age: int = edgy.IntegerField()
    class Meta:
        abstract = True
        inherit = False



class MyModel1(edgy.Model):
    model1: InheritableModel = edgy.CompositeField(inner_fields=InheritableModel)
    # note: the inherit information can be overwritten
    model2 = edgy.CompositeField(inner_fields=NonInheritableModel, inherit=True)

class MyModel2(MyModel1):
    pass
    # NonInheritableModel is gone
```
