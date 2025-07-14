# Embedding Models in Edgy

Edgy provides two primary methods for embedding models within other models, offering flexibility and control over how data is structured and accessed.

## 1. Embeddable Models

Edgy models can be seamlessly used as embeddables, treating them like fields within another model. This approach automatically copies the fields of the embedded model, prefixing them with the attribute name used for embedding, followed by an underscore (`_`).

Fields with `inherit=False` are excluded from the embedding process. This prevents fields like `PKField` or auto-injected `id` fields from being unintentionally included.

```python
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

class MyModel(edgy.Model):
    model1: ClassVar[InheritableModel] = InheritableModel
    # ClassVar is optional
    model2 = NonInheritableModel

class AnotherModel(MyModel):
    pass
    # NonInheritableModel is gone
```

**Explanation:**

* **InheritableModel:** This abstract model defines `first_name` and `last_name` fields. When `InheritableModel` is used as an embeddable in `MyModel`, these fields will be copied and prefixed.
* **NonInheritableModel:** This abstract model defines an `age` field and sets `inherit=False`. This ensures that when `NonInheritableModel` is used as an embeddable, its fields are not inherited by submodels.
* **MyModel:** This model embeds `InheritableModel` as `model1` and `NonInheritableModel` as `model2`.
* **AnotherModel:** This model inherits from `MyModel`. Due to `inherit=False` in `NonInheritableModel`, the `model2` fields are not included in `AnotherModel`.

**Key Benefits:**

* Simplified model composition: Embeddables allow you to structure complex data models by combining simpler, reusable models.
* Automatic field prefixing: Prefixes prevent naming conflicts when multiple embeddables are used in a model.
* Control over inheritance: The `inherit` parameter provides fine-grained control over which fields are inherited by submodels.

!!! Warning
    When not using `abstract=True` a field named `id` is maybe injected.

## 2. Explicit Control with CompositeField

For more explicit control over the embedding process, you can use the `CompositeField` and pass models as its `inner_fields` argument. This method provides greater flexibility in defining how embedded models are handled.

```python
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

class MyModel(edgy.Model):
    model1: InheritableModel = edgy.CompositeField(inner_fields=InheritableModel)
    # note: the inherit information can be overwritten
    model2 = edgy.CompositeField(inner_fields=NonInheritableModel, inherit=True)

class AnotherModel(MyModel):
    pass
    # NonInheritableModel is gone
```

**Explanation:**

* **CompositeField:** This field allows you to explicitly define how embedded models are handled.
* **inner_fields:** This parameter specifies the model(s) to be embedded.
* **inherit:** The `inherit` parameter can be used to override the `inherit` setting of the embedded model.

**Key Benefits:**

* Explicit control: `CompositeField` provides explicit control over which fields are embedded and how they are handled.
* Flexibility: You can override the `inherit` setting of embedded models, providing greater flexibility in model composition.
* Allows the use of other CompositeField parameters.

**When to Use Each Method:**

* Use embeddable models when you want a simple and automatic way to embed models within other models.
* Use `CompositeField` when you need more explicit control over the embedding process, such as overriding inheritance settings or using other CompositeField settings.

**In summary:**

Edgy's embedding capabilities allow you to create complex and well-structured data models by combining simpler, reusable models. Whether you choose the automatic embeddable approach or the explicit `CompositeField` method, Edgy provides the tools you need to effectively manage your data.
