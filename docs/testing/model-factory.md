# ModelFactory: Streamlining Model Stubbing in Edgy

`ModelFactory` is a powerful tool in Edgy for generating model stubs based on fakers, simplifying your testing and development workflows.

The process involves three key steps:

1.  **Factory Class Definition:** Define your factory class, customizing fakers using `FactoryField` and setting default values for model fields.
2.  **Factory Instance Creation:** Create an instance of your factory, providing specific values to be used in the model. These values can be further customized or excluded later.
3.  **Model Stub Generation:** Utilize the `build` method to generate a stubbed model instance.

This sequence allows you to efficiently create and manipulate model instances for testing and other purposes.

Example:

```python
{!> ../docs_src/testing/factory/factory_basic.py !}
```

This creates a basic `User` model factory. Let's explore more advanced features.

Example: Excluding a field (`name`) using `FactoryField`:

```python
{!> ../docs_src/testing/factory/factory_fields_exclude.py !}
```

!!! Note
    Each factory class has its own internal faker instance. To use a separate faker, provide it as the `faker` keyword parameter in the `build` method.

## Parametrization

You can customize faker behavior in two ways:

1.  **Provide parameters to faker methods.**
2.  **Provide a custom callable that can receive parameters.**

When no callback is provided, Edgy uses mappings based on the field type name (e.g., `CharField` uses the "CharField" mapping).

Example: Customizing faker parameters:

```python
{!> ../docs_src/testing/factory/factory_parametrize.py !}
```

You can also override the `field_type` in `FactoryField` for different parametrization:

```python
{!> ../docs_src/testing/factory/factory_field_overwrite.py !}
```

To override mappings for all subclasses, use the `Meta.mappings` attribute:

```python
{!> ../docs_src/testing/factory/factory_mapping.py !}
```

Setting a mapping to `None` disables stubbing by default. Re-enable it in subclasses:

```python
{!> ../docs_src/testing/factory/factory_mapping2.py !}
```

!!! Tip
    Use the `name` parameter in `FactoryField` to avoid naming conflicts with model fields.

### ModelFactoryContext

`ModelFactoryContext` replaces the `faker` argument, providing compatibility with faker while allowing access to context variables. It forwards `__getattr__` calls to the internal faker instance and provides `__getitem__` access to context items.

Known items:

* `faker`: The faker instance.
* `exclude_autoincrement`: Current `exclude_autoincrement` value.
* `depth`: Current depth.
* `callcounts`: Internal call count tracking (use `field.get_callcount()` and `field.inc_callcount()`).

You can store custom items in the context, ensuring they don't conflict with known items.

### Saving

Save generated models using the `save` parameter or the `build_and_save(...)` method (recommended):

```python
{!> ../docs_src/testing/factory/factory_save.py !}
```

!!! Warning
    `save=True` can move saving to a subloop, causing issues with `force_rollback` or limited connections. Use `build_and_save(...)` in asynchronous contexts.

### exclude_autoincrement

The `exclude_autoincrement` class parameter (default `True`) automatically excludes autoincrement columns:

```python
{!> ../docs_src/testing/factory/factory_fields_exclude_autoincrement.py !}
```

Set it to `False` to generate values for autoincrement fields.

### Setting Database and Schema

Specify a different database or schema using class or instance variables (`__using_schema__`, `database`):

```python
# class variables
class UserFactory(ModelFactory, database=database, __using_schema__="other"):
    ...
```

Or on the build method:

```python
user = factory.build(database=database, schema="other")
```

!!! Note
    `__using_schema__ = None` in `ModelFactory` uses the model's default schema, while in database models, it selects the main schema.

### Parametrizing Relation Fields

Parametrize relation fields (ForeignKey, ManyToMany, OneToOne, RelatedField) in two ways:

1.  **Pass `build()` parameters as field parameters.** Use `min` and `max` for 1-n relations.
2.  **Transform a `ModelFactory` to a `FactoryField` using `to_factory_field` or `to_list_factory_field(min=0, max=10)`.**

RelatedFields can only be parametrized using the second method.

Example: Customizing a ForeignKey:

```python
{!> ../docs_src/testing/factory/factory_to_field.py !}
```

Example: Customizing a RelatedField, ManyToMany, or RefForeignKey:

```python
{!> ../docs_src/testing/factory/factory_to_fields.py !}
```

!!! Warning
    Relationship fields can lead to large graphs. Auto-generated factories exclude unparametrized ForeignKeys, etc., by default when they have defaults or can be null.

### Special Parameters

Two special parameters are available for all fields:

* `randomly_unset`: Randomly exclude a field value.
* `randomly_nullify`: Randomly set a value to `None`.

Pass `True` for equal distribution or a number (0-100) for bias.

### Excluding Fields

Exclude fields in four ways:

1.  **Provide a field with `exclude=True`.**
2.  **Add the field name to the `exclude` parameter of `build`.**
3.  **Raise `edgy.testing.exceptions.ExcludeValue` in a callback.**
4.  **Use the `exclude_autoincrement` class variable or parameter.**

Example: Excluding a field using `exclude=True`:

```python
{!> ../docs_src/testing/factory/factory_fields_exclude.py !}
```

Example: Excluding fields using `exclude` parameter or `ExcludeValue`:

```python
{!> ../docs_src/testing/factory/factory_exclude.py !}
```

### Sequences

Generate increasing sequences using call counts:

```python
{!> ../docs_src/testing/factory/sequences.py !}
```

Reset sequences using `Factory.meta.callcounts.clear()` or pass a custom `callcounts` dictionary.

Example: Generating even sequences:

```python
{!> ../docs_src/testing/factory/sequences_even.py !}
```

Example: Generating odd sequences:

```python
{!> ../docs_src/testing/factory/sequences_odd.py !}
```

SubFactories only increment the call counts of the entry point factory. Pass a custom `callcounts` dictionary to increment other factory call counts:

```python
{!> ../docs_src/testing/factory/sequences_subfactory.py !}
```

## Build & build_and_save

The `build(...)` and `build_and_save(...)` methods generate model instances with customizable parameters:

* `faker`: Custom faker instance.
* `parameters`: Field-specific parameters or callbacks.
* `overwrites`: Direct value overrides.
* `exclude`: Fields to exclude from stubbing.
* `database`: Database to use.
* `schema`: Schema to use.
* `exclude_autoincrement`: Auto-exclude autoincrement columns.
* `save`: Synchronously save the model.
* `callcounts`: Custom call counts dictionary.

Example: Using `build` with parameters:

```python
{!> ../docs_src/testing/factory/factory_build.py !}
```

## Model Validation

Control model validation during factory generation using the `model_validation` class variable:

* `none`: No validation.
* `warn`: Warn for unsound definitions. (Default)
* `error`: Raise exceptions for unsound definitions.
* `pedantic`: Raise exceptions for Pydantic validation errors.

!!! Note
    Validation does not increment sequence call counts.

## SubFactory

This is a special object that allows you to reuse factories previously created without any issues or concerns.

Imagine the following:

```python
class UserFactory(ModelFactory):
    class Meta:
        model = User

    name = "John Doe"
    language = "en"


class ProductFactory(ModelFactory):
    class Meta:
        model = Product

    name = "Product 1"
    rating = 5
    in_stock = True
    user = SubFactory("tests.factories.UserFactory") # String import
```

Did you see? With this SubFactory object, we can simply apply factories as a `string` with the location of the factory
or passing the object directly, like the following:

```python
class UserFactory(ModelFactory):
    class Meta:
        model = User

    name = "John Doe"
    language = "en"


class ProductFactory(ModelFactory):
    class Meta:
        model = Product

    name = "Product 1"
    rating = 5
    in_stock = True
    user = SubFactory(UserFactory) # Object import
    user.parameters["randomly_nullify"] = True


class ItemFactory(ModelFactory):
    class Meta:
        model = Item

    product = SubFactory(ProductFactory)
    product.parameters["randomly_nullify"] = True
```

If the values are not supplied, Edgy takes care of generate them for you automatically anyway.
For multiple values e.g. ManyToMany you can use ListSubFactory.

You can even parametrize them given that they are FactoryFields.

!!! Tip
    Effectively SubFactories are a nice wrapper around `to_factory_field` and `to_list_factory_field` which can pull in
    from other files.

**Enhanced Explanation:**

In the first `ProductFactory` example, `user = SubFactory("tests.factories.UserFactory")` demonstrates how to use a string to import a `UserFactory`. This is particularly useful when dealing with circular imports or when factories are defined in separate modules.

* **String Import:** The string `"tests.factories.UserFactory"` specifies the fully qualified path to the `UserFactory` class. Edgy's `SubFactory` will dynamically import and instantiate this factory when needed. This approach is beneficial when your factory classes are organized into distinct modules, which is a common practice in larger projects.

* **Object Import:** The second `ProductFactory` example, `user = SubFactory(UserFactory)`, showcases direct object import. This is straightforward when the factory class is already in the current scope.

Both methods achieve the same result: creating a `User` instance within the `Product` factory. The choice between them depends on your project's structure and import preferences.
