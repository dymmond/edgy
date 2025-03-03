# Models

Have you ever wondered how time consuming and sometimes how hard is to declare a simple table
with SQLAlchemy where sometimes it can also be combersome?

What about the Django interface type for tables? Cleaner right? Well, **Edgy** although is on
the top of SQLAlchemy core, it provides a Django like experience when it comes to create models.

Do you already have a database with tables and views you would simply would like to reflect them
back instead of the opposite? [Check the reflection section](./reflection/reflection.md) for more details.

## What is a model

A model in Edgy is a python class with attributes that represents a database table as well as a pydantic model which enables serialization and validation.

In other words, it is what represents your SQL table in your codebase.

## Model dump

The `model_dump` and `model_dump_json` methods are here overloaded and supports an argument:

`show_pk` which auto-includes the the primary key fields when set to `True`. Default to the value of `__show_pk__` of models.

## Embedding

Models also doubles as embeddable; they can be used as a field template with optional prefix.

[Check the embedding section](./embedding.md).

## Declaring models

When declaring models by simply inheriting from `edgy.Model` object and define the attributes
using the edgy [Fields](./fields/index.md).

For each model defined you also need to set **one** mandatory field, the `registry` which is also
an instance of `Registry` from Edgy.

There are more parameters you can use and pass into the model such as [tablename](#the-meta-class) and
a few more but more on this in this document.

Since **Edgy** took inspiration from the interface of Django, that also means that a [Meta](#the-meta-class)
class should be declared.

```python
{!> ../docs_src/models/declaring_models.py !}
```

Although this looks very simple, in fact **Edgy** is doing a lot of work for you behind the
scenes.

Edgy models are a bit opinionated when it comes to `ID` and this is to maintain consistency
within the SQL tables with field names and lookups.

### Strict models

Sometimes you want more input validation. E.g. non-existing fields are not just ignored but raise an error
or the input type is not coerced into the right type but raises an error instead.

For this the `StrictModel` model can be used. Otherwise it behaves like a normal Model.

There is no strict version of a `ReflectModel` because the laxness is required.


### Loading models

You may have the models distributed among multiple files and packages.
To ensure the models can self-register we need to ensure the files load.
Previously this was done with `model_apps` in the `Migrate` object but this approach is deprecated and
didn't allow multiple registries.
Edgy has now a special setting `preloads` in [Settings](settings.md). Here it is possible to provide the import pathes
and the corresponding files are loaded.
It is also possible to point to a function via `module_path:fn` which is executed without argument and expected to load the modules.

### Special attributes

There are few special attributes which can be set

- `database`: Different database/access current database of model. Should be in registry extra. It is set per instance when using queries.
- `__using_schema__`: Different schema. The schema must be created first. Default is Undefined. It is set per instance for tenant models.
- ``
These attributes work on instances as well as classes.

There are a few more exotic ones:

- `__require_model_based_deletion__`: (Default False): Enforce a deletion in edgy instead of the database (Query iterates through models and deletes each explicitly). This is quite imperformant, so only set it if you really require that the delete method of a model is called.
- `__reflected__`: Only read but don't set it. It shows if a model has the reflected state.

### Attention

If no `id` is declared in the model, **Edgy** will automatically generate an `id` of type
`BigIntegerField` and **automatically becoming the primary key**.

```python
{!> ../docs_src/models/declaring_models_no_id.py !}
```

### Restrictions with primary keys

Earlier there were many restrictions. Now they were lifted

### Controlling collision behaviour

Earlier models were simply replaced when defining a model with the same name or adding such.

Now the default is to error when a collision was detected, or in case the `on_conflict` parameter was set, either
a `replace` or `keep` executed.

``` python
{!> ../docs_src/models/on_conflict.py !}
```

#### What you should not do

##### Declaring an IntegerField as primary key without autoincrement set

Because of backward compatibility we set for an IntegerField or BigIntegerField which is declared as primary key
the autoincrement option to `True`. So you still need to explicitly set `autoincrement=False` to turn this off.

This will change in future. The default will be `False`.

!!! Warning
    For every model only one IntegerField/BigIntegerField can be set to autoincrement=True.

#### What you can do

The examples
are applied to any [field](./fields/index.md) available in **Edgy**.


##### Declaring a model primary key different from ID

```python hl_lines="11-12"
{!> ../docs_src/models/declaring_models_pk_no_id.py !}
```

##### Multiple primary keys

This is novel and maybe a bit buggy in combination with ForeignKeys.

##### Declaring a model with ID and without default and autoincrement

When declaring an `id`, unless the field type is [IntegerField](./fields/index.md#integerfield) or
[BigIntegerField](./fields/index.md#bigintegerfield), you have to provide the primary key when creating the object.

```python hl_lines="9"
{!> ../docs_src/models/pk_no_default.py !}
```

##### Declaring a model primary key with different field type

This is for an explicit `primary_key` that you don't want to be the default, for example, a
[UUIDField](./fields/index.md#uuidfield).

```python hl_lines="11"
{!> ../docs_src/models/pk_with_default.py !}
```

##### Declaring a model with default primary key

If you don't want to be bothered and you are happy with the defaults generated by **Edgy**,
then you can simply declare the model without the `id`.

```python
{!> ../docs_src/models/default_model.py !}
```

##### Customizing the deletion variant

By default a database only deletion is used where possible when using the QuerySet delete method.

If you want to force the QuerySet calling the delete method of the model instead,
you can set the class variable:

`__require_model_based_deletion__ = True`

##### Copying a model to a new registry

We have now a method:

`model.copy_edgy_model(registry=None, name="")`

to copy a model class and optionally add it to an other registry.

You can add it to a registry later by using:

`model_class.add_to_registry(registry, name="", database=None, replace_related_field=...)`

In fact the last method is called when the registry parameter of `copy_edgy_model` is not `None`.


### The Meta class

When declaring a model, it is **crucial** having the `Meta` class declared. There is where you
declare the `metadata` needed for your models.

Currently the available parameters for the meta are:

* **registry** - The [registry](./registry.md) instance for where the model will be generated.

* **tablename** - The name of the table in the database, **not the class name**.

    <sup>Default: `name of class pluralised`<sup>

* **abstract** - If the model is abstract or not. If is abstract, then it won't generate the
database table.

    <sup>Default: `False`<sup>

* **unique_together** - The unique constrainsts for your model.

    <sup>Default: `None`<sup>

* **indexes** - The extra custom indexes you want to add to the model

### Registry

Working with a [registry](./registry.md) is what makes **Edgy** dynamic and very flexible with
the familiar interface we all love. Without the registry, the model doesn't know where it should
get the data from.

Imagine a `registry` like a bridge because it does exactly that.

Let us see some examples in how to use the registry with simple design and with some more complex
approaches.

#### In a nutshell

```python hl_lines="5 13"
{!> ../docs_src/models/registry/nutshell.py !}
```

As you can see, when declaring the `registry` and assigning it to `models`, that same `models` is
then used in the `Meta` of the model.

#### With inheritance

Yes, you can also use the model inheritance to help you out with your models and avoid repetition.

```python hl_lines="5 14"
{!> ../docs_src/models/registry/inheritance_no_repeat.py !}
```

As you can see, the `User` and `Product` tables are inheriting from the `BaseModel` where the
`registry` was already declared. This way you can avoid repeating yourself over and over again.

This can be particularly useful if you have more than one `registry` in your system and you want
to split the bases by responsabilities.

#### With abstract classes

What if your class is abstract? Can you inherit the registry anyway?

Of course! That doesn't change anything with the registry.

```python hl_lines="5 14"
{!> ../docs_src/models/registry/inheritance_abstract.py !}
```

### Table name

This is actually very simple and also comes with defaults. When creating a [model](#declaring-models)
if a `tablename` field in the `Meta` object is not declared, it will pluralise the python class.

#### Model without table name

```python
{!> ../docs_src/models/tablename/model_no_tablename.py !}
```

As mentioned in the example, because a `tablename` was not declared, **Edgy** will pluralise
the python class name `User` and it will become `users` in your SQL Database.

#### Model with a table name

```python hl_lines="13"
{!> ../docs_src/models/tablename/model_with_tablename.py !}
```

Here the `tablename` is being explicitly declared as `users`. Although it matches with a
puralisation of the python class name, this could also be something else.

```python hl_lines="13"
{!> ../docs_src/models/tablename/model_diff_tn.py !}
```

In this example, the `User` class will be represented by a `db_users` mapping into the database.

!!! Tip
    Calling `tablename` with a different name than your class it doesn't change the behaviour
    in your codebase. The tablename is used **solely for SQL internal purposes**. You will
    still access the given table in your codebase via main class.


### Abstract

As the name suggests, it is when you want to declare an abstract model.

Why do you need an abstract model in the first place? Well, for the same reason when you need to
declare an abstract class in python but for this case you simply don't want to generate a table
from that model declaration.

This can be useful if you want to hold common functionality across models and don't want to repeat
yourself.

The way of declaring an abstract model in **Edgy** is by passing `True` to the `abstract`
attribute in the [meta](#the-meta-class) class.

### Explicitly disable registry registration

Sometimes you want to add a model manually to the registry and not to retrieve a registry by the parents.
This can be archived by setting Meta registry to False.

#### In a nutshell

In this document we already mentioned abstract models and how to use them but let us use some more
examples to be even clear.


```python hl_lines="10"
{!> ../docs_src/models/abstract/simple.py !}
```

This model itself does not do much alone. This simply creates a `BaseModel` and declares the
[registry](#registry) as well as declares the `abstract` as `True`.

#### Use abstract models to hold common functionality

Taking advantage of the abstract models to hold common functionality is usually the common use
case for these to be use in the first place.

Let us see a more complex example and how to use it.

```python hl_lines="10"
{!> ../docs_src/models/abstract/common.py !}
```

This is already quite a complex example where `User` and `Product` have both common functionality
like the `id` and `description` as well the `get_description()` function.

#### Limitations

You can do **almost everything** with abstract models and emphasis in **almost**.

Abstract models do not allow you to:

* **Declare** [managers](./managers.md).
* **Declare** [unique together](#unique-together)

This limitations are intentional as these operations should be done for [models](#declaring-models)
and not abstact models.

### Unique together

This is a very powerful tool being used by almost every single SQL database out there and extremely
useful for database design and integrity.

If you are not familiar with the concept, a unique together enforces records to be
**unique within those parameters** when adding a record to a specific table.

Let us see some examples.

#### Simple unique together

The simplest and cleanest way of declaring a unique together. There are actually **two** ways of
declaring this simple **unique**. Via [edgy field](./fields/index.md) directly or via
`unique_together` in the [meta](#the-meta-class) class.

##### Within the edgy field

```python hl_lines="10"
{!> ../docs_src/models/unique_together/simple.py !}
```

In the field you can declare directly `unique` and that is about it.

##### With unique_together

```python hl_lines="15"
{!> ../docs_src/models/unique_together/simple2.py !}
```

The `unique_together` expects one of the following:

* **List of strings**.
* **List of tuple of strings**.
* **List of tuples of strings**.
* **List of tuples of strings as well as strings**
* **A list of UniqueConstraint instances**.

If none of these values are provided, it will raise a `ValueError`.

#### Complex unique together

Now, we all know that using simple uniques is easier if automatically declared within the
[edgy field](./fields/index.md) an using the [meta](#the-meta-class) for only one field is overkill.

You take advantage of the `unique_together` when something more complex is needed and not limited
to one database field only.

##### When you need more than one field, independently, to be unique

```python hl_lines="15"
{!> ../docs_src/models/unique_together/complex_independent.py !}
```

Now here is the tricky part. If you wanted to have **together** non-duplicate records with the
same `email` and `name`, this is **not doing that**. This is in fact saying unique emails and
unique names independent of each other.

This is useful but depends on each use case.

For this we used a **list of strings**.

##### When you need more than one field, together, to be unique

```python hl_lines="15"
{!> ../docs_src/models/unique_together/complex_together.py !}
```

Did you notice the difference? In this case, when you add a new record to the database it will
validate if the `name` and `email` together already exists. They are treated as one.

For this we used a **list of tuple of strings**.

##### When you need more than combined key, to be unique

```python hl_lines="17-21"
{!> ../docs_src/models/unique_together/complex_combined.py !}
```

Now here is where the things get complex and exciting. As you can see, you can add different
variations of the fields combined and generate with whatever complexity you need for your cases.

For this we used a **list of tuples of strings**.

##### When you want to mix it all

There are also cases when you want to mix it all up and this is also possible.

```python hl_lines="17-22"
{!> ../docs_src/models/unique_together/complex_mixed.py !}
```

Did you notice the different compared to the [previous](#when-you-need-more-than-combined-key-to-be-unique)
example? This time we added a string `is_active` to the mix.

This will make sure that `is_active` is also unique
(although in general, for this case would not make too much sense).

For this we used a **list of tuples of strings as well as strings**.

##### When you use UniqueConstraint instances

This is another clean way of adding the unique together constrainst. This can be used also with
the other ways of adding unique together shown in the above examples.

```python hl_lines="2 17-22"
{!> ../docs_src/models/unique_together/constraints/complex.py !}
```

**Or mixing both**

```python hl_lines="2 17-22"
{!> ../docs_src/models/unique_together/constraints/mixing.py !}
```

### Indexes

Sometimes you might want to add specific designed indexes to your models. Database indexes also
somes with costs and you **should always be careful** when creating one.

If you are familiar with indexes you know what this means but if you are not, just have a quick
[read](https://www.codecademy.com/article/sql-indexes) and get yourself familiar.

There are different ways of declaring an index.

Edgy provides an `Index` object that must be used when declaring models indexes or a
`ValueError` is raised.

```python
from edgy import Index
```
#### Parameters

The `Index` parameters are:

* **fields** - List of model fields in a string format.
* **name** - The name of the new index. If no name is provided, it will generate one, snake case
with a suffix `_idx` in the end. Example: `name_email_idx`.
* **suffix** - The suffix used to generate the index name when the `name` value is not provided.

Let us see some examples.

#### Simple index

The simplest and cleanest way of declaring an index with **Edgy**. You declare it directly in
the model field.

```python hl_lines="10"
{!> ../docs_src/models/indexes/simple.py !}
```

#### With indexes in the meta

```python hl_lines="15"
{!> ../docs_src/models/indexes/simple2.py !}
```

#### With complex indexes in the meta

```python hl_lines="16-19"
{!> ../docs_src/models/indexes/complex_together.py !}
```

### Constraints

Plain sqlalchemy constraints can be passed via the meta.constraints parameter.

This is useful for CheckConstraints (despite pydantic can handle most cases better).

```python hl_lines="17"
{!> ../docs_src/models/constraints.py !}
```

!!! Note
    This operates on column level not on field level. The column key is relevant.

## Meta info attributes

The metaclass also calculates following readonly attributes:

- `special_getter_fields` (set): Field names with `__get__` function. This is used for the pseudo-descriptor `__get__` protocol for fields.
- `excluded_fields` (set): Field names of fields with `exclude=True` set. They are excluded by default.
- `secret_fields` (set): Field names of fields with `secret=True` set. They are excluded by default when using `exclude_secret`.
- `input_modifying_fields` (set): Field names of fields with a `modify_input` method. They are altering the input kwargs of `transform_input` (setting to model) and `extract_column_values`.
- `post_save_fields` (set): Field names of fields with a `post_save_callback` method.
- `pre_save_fields` (set): Field names of fields with a `pre_save_callback` method.
- `post_delete_fields` (set): Field names of fields with a `post_save_callback` method.
- `foreign_key_fields` (set): Field names of ForeignKey fields. Note: this does not include ManyToMany fields but their internal ForeignKeys.
- `relationship_fields` (set): Field names of fields inheriting from RelationshipField.
- `field_to_columns` (pseudo dictionary): Maps a fieldname to its defined columns.
- `field_to_column_names` (pseudo dictionary): Maps a fieldname to its defined column keys. Uses internally `field_to_columns`.
- `columns_to_field` (pseudo dictionary): Maps a column key to its defining field.

Some other interesting attributes are:

- `multi_related` (set[tuple[str, str]]): Holds foreign_keys used by ManyToManyFields when being used as a through model. Is empty for non-through models.
- `fields` (pseudo dictionary): Holds fields. When setting/deleting fields it updates the attributes.
- `model` (model_class): This attribute is special in it's way that it is not retrieved from a meta class. It must be explicitly set.
                         This has implications for custom MetaInfo. You either replace the original one by passing meta_info_class as metaclass argument or set it in your overwrite manually.
