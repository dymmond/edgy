# ModelFactory

A ModelFactory is a faker based model stub generator.

In the first step, building the factory class, you can define via `FactoryField`s customizations of the parameters passed
for the fakers for the model.

The second step, is making a factory instance. Here can values be passed which should be used for the model. They are baked in
the factory instance. But you are able to overwrite them in the last step or to exclude them.

The last step, is building a stub model via `build`. This is an **instance-only** method not like the other build method other model definitions.

In short the sequence is like follows:

Factory definition -> Factory instance -> Factory build method -> stubbed Model instance to play with.

You can reuse the factory instance to produce a lot of models.

Example:



!!! Note
    Every Factory class has an own internal faker instance. If you require a separate faker you have to provide it in the build method
    as `faker` keyword parameter.

## Parametrize

For customization you have two options: provide parameters to the corresponding faker method or to provide an own callable which can also receive parameters.
Note however relationship fields are a bit different.

Normally you

For paremtrii


### Special parameters

There are two special parameters which are always available for all fields:

- randomly_unset
- randomly_nullify

The first randomly excludes a field value. The second randomly sets a value to None.
You can either pass True for a equal distribution or a number from 0-100 to bias it.

## Build

The central method for factories is `build()`.

## Model Validation

By default a validation is executed if the model can ever succeed in generation. If not an error
is printed but the model still build.
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
