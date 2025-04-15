# Custom fields

## Factory fields

If you merely want to customize an existing field in `edgy.core.db.fields` you can just inherit from it and provide the customization via the `FieldFactory` (or you can use `FieldFactory` directly for handling a new sqlalchemy type).
Valid methods to overwrite are `__new__`, `get_column_type`, `get_pydantic_type`, `get_constraints`, `build_field` and `validate` as well as you can overwrite many field methods
by defining them on the factory (see `edgy.core.db.fields.factories` for allowed methods). Field methods overwrites must be classmethods which take as first argument after
the class itself the field object and a keyword arg original_fn which can be None in case none was defined.

For examples have a look in `edgy/core/db/fields/core.py`.


!!! Note
    You can extend in the factory the overwritable methods. The overwritten methods are not permanently overwritten. After init it is possible to change them again.
    A simple example is in `edgy/core/db/fields/exclude_field.py`. The magic behind this is in  `edgy/core/db/fields/factories.py`.

!!! Tip
    For global constraints you can overwrite the `get_global_constraints` field method via the factory overwrite. This differs from `get_constraints` which is defined on factories.

## Extended, special fields

If you want to customize the entire field (e.g. checks), you have to split the field in 2 parts:

- One inherits from `edgy.db.fields.base.BaseField` (or one of the derived classes) and provides the missing parts. It shall not be used for the Enduser (though possible).
- One inherits from `edgy.db.fields.factories.FieldFactory`. Here the field_bases attribute is adjusted to point to the Field from the first step.

Fields have to inherit from `edgy.db.fields.base.BaseField` and to provide following methods to work:

- `get_columns(self, field_name)` - returns the sqlalchemy columns which should be created by this field.
- `clean(self, field_name, value, to_query=False)` - returns the cleaned column values. to_query specifies if clean is used by the query sanitizer and must be more strict (no partial values).

Additional they can provide/overwrite following methods:

* `operator_to_clause` - Generates clauses for db from the result of clean. Implies clean is called with `for_query=True`.
* `__get__(self, instance, owner=None)` - Descriptor protocol like get access customization. Second parameter contains the class where the field was specified.
  To prevent unwanted loads operate on the instance `__dict__`. You can throw an AttributeError to trigger a load.
* `__set__(self, instance, value)` - Descriptor protocol like set access customization. Dangerous to use. Better use to_model.
* `to_model(self, field_name)` - like clean, just for setting attributes or initializing a model. It is also used when setting attributes or in initialization (phase contains the phase where it is called). This way it is much more powerful than `__set__`.
* `get_embedded_fields(self, field_name, fields)` - Define internal fields.
* `get_default_values(self, field_name, cleaned_data)` - returns the default values for the field. Can provide default values for embedded fields. If your field spans only one column you can also use the simplified get_default_value instead. This way you don't have to check for collisions. By default get_default_value is used internally.
* `get_default_value(self)` - return default value for one column fields.
* `get_global_constraints(self, field_name, columns, schemes)` - takes as second parameter (self excluded) the columns defined by this field (by get_columns). Returns a global constraint, which can be multi-column. The last one provides the schemes in descending priority.
* `modify_input(name, kwargs)`: Modifying the input (kwargs is a dict). E.g. providing defaults only when loaded from db or collecting fields and columns for a
  multi column, composite field (e.g. FileField). Note: this method is very powerful. You should only manipulate sub-fields and columns belonging to the field.
* `embed_field(prefix, new_fieldname, owner=None, parent=None)`: Controlling the embedding of the field in other fields. Return None to disable embedding.

You should also provide an init method which sets following attributes (when using normal, single column fields):

* `column_type` - either None (default) or the sqlalchemy column type
* `inject_default_on_partial_update` - Add default value despite being a partial update. Useful for implementing `auto_now` or other fields which should change on every update.

!!! Note
    Instance checks can also be done against the `field_type` attribute in case you want to check the compatibility with other fields (composite style).
    The `annotation` field parameter is for pydantic (automatically set by factories).
    For examples have a look in `tests/fields/test_composite_fields.py` or in `edgy/core/db/fields/core.py`.

!!! Note
    The CURRENT_MODEL_INSTANCE is always the model instance in contrast to the CURRENT_INSTANCE ContextVar.

For advanced internal stuff you can use the callback fields. They will cause an different, less efficient code-path when updating, inserting or deleting models having fields with such attributes (can be mitigated by only updating non-effected fields). This is only true for QuerySet because model instances have no efficient sql shortcuts.
So the best thing is to only set them if you require them. See e.g. RelatedField how to do that. You will need them if you have async code you want to execute in the field cleaning phase.

* `async def pre_save_callback(value, original_value, is_update) -> dict`: Affects updates/insert. Can be used to parse special data-types to multiple db columns directly. It will be executed after `extract_column_values`. Advantage over clean: we have always an instance (saved/unsaved) and it is only called when actually saving.
* `async def post_save_callback(value, is_update) -> dict`: Affects updates/inserts. Can be used to save files after db-updates succeed. It is executed after all fields are set to the instance via modify_input.
* `async def post_delete_callback(value) -> None`: Affects deletions. Automatically triggers a model based deletion (instead of using fast sql, the deletion takes place row by row). This is used for ContentTypes.


!!! Note
    The callbacks have no CURRENT_PHASE set. Use the is_update parameter to figure out what operation is executed.

## Tricks

### Using for_query

`clean` is required to clean the values for the db. It has an extra parameter `for_query` which is set
in a querying context (searching something in the db).

When using a multi-column field, you can overwrite `operator_to_clause`. You may want to adjust clean called with
`for_query=True` so it returns are suitable holder object (e.g. dict) for the fieldname.
See `tests/fields/test_multi_column_fields.py` for an example.

### Using phases

The `CURRENT_PHASE` ContextVariable contains the current phase. If used outside of a model context it defaults to an empty string.

Within a model context it contains the current phase it is called for:

* `init`: Called    in model `__init__`.
* `init_db`: Called in model `__init__` when loaded from a row.
* `set`: Called in model `__setattr__` (when setting an attribute).
* `load`: Called after load. Contains db values.
* `post_insert`: Called after insert. Arguments are the ones passed to save.
* `post_update`: Called after update. Arguments are the ones passed to save.

For  `extract_column_values` following phases exist (except called manually):

* `prepare_insert`: Called in extract_column_values for insert.
* `prepare_update`: Called in extract_column_values for update.
* `compare`: Called when comparing model instances.

### Using the field context

Field methods can access a context variable named FIELD_CONTEXT. It holds a reference to the current field instance as `field` item.
You can manipulate it like you wish but it will be resetted after the field has been transformed.

### Using the instance

There are 2 ContextVar named `CURRENT_INSTANCE` and `CURRENT_MODEL_INSTANCE`. `CURRENT_INSTANCE` is the executing instance of a QuerySet or Model while
`CURRENT_MODEL_INSTANCE` is always a model instance or `None`. When calling manually also `CURRENT_INSTANCE` can be `None`.
They are available during setting an attribute, `transform_input` and `extract_column_values` calls when set as well as in the `pre_save_callback` or `post_save_callback` hooks.
This implies you can use them in all sub methods like get_default...

Note: When using in-db updates of QuerySet there is no instance.

#### Finding out which values are explicit set

The `EXPLICIT_SPECIFIED_VALUES` ContextVar is either None or contains the key names of the explicit specified values.
It is set in `save` and `update`.

#### Saving variables on Field

You can use the field as a store for your customizations. Unconsumed keywords are set as attributes on the BaseField object.
But if the variables clash with the variables used for Columns or for pydantic internals, there are unintended side-effects possible.


### Field returning persistent, instance aware object

For getting an immutable object attached to a Model instance, there are two ways:

- Using Managers (by default they are instance aware)
- Using fields with `__get__` and `to_model`.

The last way is a bit more complicated than managers. You need to consider 3 ways the field is affected:

1. `__init__` and `load`: Some values are passed to the field. Use `to_model` for providing an initial object with the CURRENT_INSTANCE context var.
    Note: this doesn't gurantee the initialization. We still need the  `__get__`-
2. `__getattr__` here the object can get an instance it can attach to. Use `__get__` for this.
3. Set access. Either use `__set__` or `to_model` so it uses the old value.

### Nested loads with `__get__`

Fields using `__get__` must consider the context_var `MODEL_GETATTR_BEHAVIOR`. There are two modes to consider:

1. `passdown`: getattr access returns `AttributeError` on missing attributes. The first time an `AttributeError` is issued a load is issued when neccessary and the mode switches to `coro`. This can be overwritten in composite fields.
2. `coro`: `__get__` needs to issue the load itself (in case this is wanted) and to handle returned coroutines. AttributeErrors are passed through.

The third mode `load` is only relevant for models and querysets.

## Customizing fields after model initialization

Dangerous! There can be many side-effects, especcially for non-metafields (have columns or attributes).

If you just want to remove a field ExcludeField or the inherit flags are the ways to go.

Adding, replacing or deleting a field is triggering automatically a required invalidation and auto-registers in pydantic model_fields.
For non-metafields you may need to rebuild the model.

If you want to add/delete a Field dynamically, check `edgy/core/db/models/metaclasses.py` or `edgy/core/connection/registry.py`
first what is done. Sometimes you may need to update the annotations.
