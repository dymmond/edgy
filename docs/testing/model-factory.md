# ModelFactory

A ModelFactory is a faker based model stub generator.

In the first step, building the factory class, you can define via `FactoryField`s customizations of the parameters passed
for the fakers for the model.

The second step, is making a factory instance. Here can values be passed which should be used for the model. They are baked in
the factory instance. But you are able to overwrite them in the last step or to exclude them.

The last step, is building a stub model via `build`. This is an **instance-only** method not like the other build method other model definitions.

In short the sequence is:

Factory definition -> Factory instance -> Factory build method -> stubbed Model instance to play with.

You can reuse the factory instance to produce a lot of models.

Example:

```python
{!> ../docs_src/testing/factory/factory_basic.py !}
```

Now we have a basic working model. Now let's get more complicated. Let's remove the `name` field via factory fields:

```python
{!> ../docs_src/testing/factory/factory_fields_exclude.py !}
```

!!! Note
    Every Factory class has an own internal faker instance. If you require a separate faker you have to provide it in the build method
    as `faker` keyword parameter.

## Parametrize

For customization you have two options: provide parameters to the corresponding faker method or to provide an own callable which can also receive parameters.
When no callback is provided the mappings are used which use the field type name of the corresponding edgy field.

E.g. CharFields use the "CharField" mapping.

```python
{!> ../docs_src/testing/factory/factory_parametrize.py !}
```

You can also overwrite the field_type on FactoryField base. This can be used to parametrize
fields differently. E.g. ImageFields like a FileField or a CharField like PasswordField.

```python
{!> ../docs_src/testing/factory/factory_field_overwrite.py !}
```

In case you want to overwrite a mapping completely for all subclasses you can use the Meta `mappings` attribute.

```python
{!> ../docs_src/testing/factory/factory_mapping.py !}
```

Setting a mapping to `None` will disable a stubbing by default.
You will need to re-enable via setting the mapping in a subclass to a mapping function.

```python
{!> ../docs_src/testing/factory/factory_mapping2.py !}
```

!!! Tip
    You can name a FactoryField differently and provide the name parameter explicitly. This way it is possible to workaround occluded fields.

### Saving

Saving can be done with save parameter or the `build_and_save(...)` method (more recommended).

```python
{!> ../docs_src/testing/factory/factory_save.py !}
```

!!! Warning
    The parameter `save=True` can move the saving to a subloop.
    This can be problematic with `force_rollback` active or in case you have very few connections to use.
    When possible and in an asynchronous context it is highly recommended to use `build_and_save(...)` instead.

### exclude_autoincrement

A special class parameter is `exclude_autoincrement`. It can be used to auto-exclude the autoincrement column from beeing set.
This is an alternative to manually exclude the auto-generated id field. It is by default `True`. Set it to `False` to get an stubbed value for an
autoincrement field (in most cases `id` this can change in case the wrapped model defines primary key fields).

```python
{!> ../docs_src/testing/factory/factory_fields_exclude_autoincrement.py !}
```

### Setting database and schema

By default the database and schema of the model used is unchanged. You can however provide an other database or schema than the default by defining
them as class or instance variables (not by keyword arguments) on a Factory.
The syntax is the same as the one used for database models, you define them on the main model. You can also overwrite them one-time in the build method.

- `__using_schema__` (str or None)
- `database` (Database or None)

!!! Note
    There is a subtle difference between database models and ModelFactories concerning `__using_schema__`.
    When `None` in `ModelFactory` the default of the model is used while in database models None selects the main schema.


### Parametrizing relation fields

Relation fields are fields like ForeignKey ManyToMany, OneToOne and RelatedField.

To parametrize relation fields there are two variants:

1. Pass `build()` parameters as field parameters. For 1-n relations there are two extra parameters min (default 0), max (default 10), which allow to specify how many
   instances are generated.
2. Transform a ModelFactory to a FactoryField.

The first way cannot be used with RelatedFields, which are automatically excluded.
You can however pass values to them via the second way.

To transform a ModelFactory there are two helper classmethods:

1. `to_factory_field`
2. `to_list_factory_field(min=0, max=10)`


Example for custom parametrization of a ForeignKey

```python
{!> ../docs_src/testing/factory/factory_to_field.py !}
```

Example for custom parametrization of a RelatedField, a ManyToMany or a RefForeignKey

```python
{!> ../docs_src/testing/factory/factory_to_fields.py !}
```

!!! Warning
    Relationship fields can easily lead to big graphs when not excluded in factory and provided manually. Especially dangerous
    are ForeignKeys to the same model. They can lead to infinite recursion.
    For this reason the autogenerated ModelFactories for relationship fields exclude by default all unparametrized ForeignKeys, ...
    when they have a default or can be null.

### Special parameters

There are two special parameters which are always available for all fields:

- randomly_unset
- randomly_nullify

The first randomly excludes a field value. The second randomly sets a value to None.
You can either pass True for a equal distribution or a number from 0-100 to bias it.

### Excluding a field

To exclude a field there are four ways

- Provide a field with `exclude=True`. It should be defined under the name of the value.
- Add the field name to the exclude parameter of build.
- Raise `edgy.testing.exceptions.ExcludeValue` in a callback.
- The `exclude_autoincrement` classvar or parameter.

Let's revisit one of the first examples. Here the id field is excluded by a different named FactoryField.

```python
{!> ../docs_src/testing/factory/factory_fields_exclude.py !}
```

Note: However that the FactoryField can only be overwritten by its provided name or in case it is unset its implicit name.
When multiple fields have the same name, the last found in the same class is overwritting the other.

Otherwise the mro order is used.

The `exclude_autoincrement` is explained above in [exclude_autoincrement](#exclude_autoincrement).

Here an example using both other ways:

```python
{!> ../docs_src/testing/factory/factory_exclude.py !}
```

## Build & build_and_save

The central method for factories are `build(...)` and `build_and_save(...)` for saving after. It generates the model instance.
It has also some keyword parameters for post-customization. They are also available for default relationship fields
or for wrapping factory fields via the `to_factory_field` or `to_list_factory_field` methods.

The parameters are:

- **faker** (not available for factories for relationship fields. Here is the provided faker or faker of the parent model used). Provide a custom Faker instance.
  This can be useful when the seed is modified.
- **parameters** ({fieldname: {parametername: parametervalue} | FactoryCallback}): Provide per field name either a callback which returns the value or parameters.
- **overwrites** ({fieldname: value}): Provide the value directly. Skip any evaluation
- **exclude** (e.g. {"id"}): Exclude the values from stubbing. Useful for removing the autogenerated id.
- **database** (Database | None | False): Use a different database. When `None` pick the one of the ModelFactory if available, then fallback to the model.
  When `False`, just use the one of the model.
- **schema** (str | None | False):  Use a different schema. When `None` pick the one of the ModelFactory if available, then fallback to the model.
  When `False`, just use the one of the model.
- **exclude_autoincrement** (None | bool): Auto-exclude the column with the `autoincrement` flag set. This is normally the injected id field.
- **save** (Bool, only build): Save synchronously the model. It is a shortcut for `run_sync(factory_instance.build_and_save(...))`. By default `False`.

```python
{!> ../docs_src/testing/factory/factory_build.py !}
```

## Model Validation

By default a validation is executed if the model can ever succeed in generation. If not an error
is printed but the model still builds.
If you dislike this behaviour, you can disable the implicit model validation via:

```python
class UserFactory(ModelFactory, model_validation="none"):
    ...
```

You have following options:

- `none`: No implicit validation.
- `warn`: Warn for unsound factory/model definitions which produce other errors than pydantic validation errors. Default.
- `error`: Same as warn but reraise the exception instead of a warning.
- `pedantic`: Raise even for pydantic validation errors.

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
    user = SubFactory("accounts.tests.factories.UserFactory")


class ItemFactory(ModelFactory):
    class Meta:
        model = Item

    product = SubFactory("products.tests.ProductFactory")
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
    user = SubFactory(UserFactory)


class ItemFactory(ModelFactory):
    class Meta:
        model = Item

    product = SubFactory(ProductFactory)
```

If the values are not supplied, Edgy takes care of generate them for you automatically anyway.
