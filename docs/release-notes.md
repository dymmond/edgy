---
hide:
  - navigation
---


# Release Notes

## 0.33.0

### Added

- Allow multiple admins.
- Add asgi multiplexing middleware (`edgy.contrib.lilya.middleware.EdgyMiddleware`).
- Support for `isnull` operator for querysets on a field.
- Support for `isempty` operator for querysets on a field.
- Support `NumberedPaginator` as alias for `Paginator` (n fact `Paginator` is an alias of `NumberedPaginator`).

## Changed

- `JSONField` uses now `JSONB` by default for postgresql (and only for postgresql).
- Slightly changed `InspectDB` internal interface.
- When using a relation, all queryset operations are by default executed on the target model except for ManyToManyFields with `embed_through=""` (default).
  In this case the reference is the through model. E.g.
  ``` python
  class User(edgy.Model):
    name = edgy.CharField(max_length=255)
      ...
  class Product(edgy.Model):
      name = edgy.CharField(max_length=255)
      users = edgy.ManyToMany("User", related_name="products", through_tablename=edgy.NEW_M2M_NAMING)
      users2 = edgy.ManyToMany("User", embed_through="", related_name="products", through_tablename=edgy.NEW_M2M_NAMING)
      users3 = edgy.ManyToMany("User", embed_through="embedded", related_name="products", through_tablename=edgy.NEW_M2M_NAMING)

  product: Product = ...
  await product.users.order_by("name")
  # use old way
  await product.users2.order_by("user__name")
  # sort for product name
  await product.users3.order_by("embedded__product__name")
  ```

### Fixed

- Status code when page in admin was not found.
- Fix issues with json-editor ajax and enums by simply inlining all schemas and disabling ajax.
- For the json schema view: don't use ref_template, it isn't well supported and leads to problems with enums.
- Fix crash when `None` is passed to CompositeField.
- Fix values_list when using relation queryset.
- Fix values_list when using only string.
- Fix performance when using relation queryset.
- Fix order_by when using relation queryset.
- Fix crash when `None`is passed to `IPAddressField`.

### Breaking

- `JSONField` uses now postgresql `JSONB` by default for postgresql (and only for postgresql).
  This may can cause an extra migration (because variants are used). If this is unwanted,
  add: `no_jsonb=True` to `JSONField`.
- By fixing the column retrieval of order_by, ... we may break userspace. Fix it by removing the now superfluous prefix. `embed_through=""` is not affected as we have here the old interface.

## 0.32.5

### Fixed

- Admin with foreign keys as primary keys.
- Revisioning with `auto_now` as primary key.
- Fix crash with `auto_now_add` as primary key.
- Fix "$defs" not matching def names. This fixes problems with enums which appear multiple times and reduces requests.
- Fix using ForeignKeys in embedded models/CompositeFields when the embedded model has no registry set (e.g. abstract).
- Improve admin UI.
- Add some extra filters and option to make Primarykeys read-only in marshall.

### Changed

- Remove by default read-only fields from admin create/update.
- Remove by default autoincrement fields from admin create.
- Make PrimaryKeys read-only for update (they will be removed because they are read-only until we have a better solution).
- `FileStruct` name have a minimal length of 1.

## 0.32.4

### Fixed

- Fix incorrect documentation for admin.
- Fix admin_serve behind a reverse proxy.

## 0.32.3

### Fixed

- Add proper error for python>=3.12, when marshall_config is added as instance annotation.

## 0.32.2

### Added

- Add model search in admin.

### Changed

- Split out base head from admin into an extra template. This improves the customizability and allows to self-host.

### Fixed

- Circular import errors with marshalls.
- Missing typing export for PGArrayField.
- Proper escape json values.

## 0.32.1

### Added

- Customization hooks for admin.
- Expose marshalls in a global `edgy.marshalls` namespace.
- Add authentication for `admin_serve`.

### Changed

- Don't import mixins from sub-modules in `edgy.core.db.models.mixins` (to prevent import-cycles).
- Move Metaclass from `BaseMarshall` to `Marshall`.
- `admin_prefix_url` is automatically inferred.
- Require `session` for embedding admin.

### Fixed

- Allow marshalls with the name `Marshall`.
- Fix repr on marshalls.
- Fix recent_models.

## 0.32.0

### Added

- Allow partial Marshalls.
- Add admin_serve for modifying db.
- FileFields have now a json-schema mode. You can pass a FileStruct like dict.

### Changed

- `_loaded_or_deleted` is now `_db_loaded_or_deleted`. The former name is now deprecated.
- `_loaded_or_deleted` is splitted in `_db_loaded` and `_db_deleted`.
- Migrations show now tracebacks when manual migration of objects fails.
- Bump python requirement to python 3.10 to align with (optional) dependencies.

### Fixed

- Recursive saving.
- Various json schema fixes.
- Inherit register_default.

### Breaking

- Python 3.9 is no longer supported.
- Remove long-deprecated `edgy_setattr` alias for `object.__setattr__`.

## 0.31.3

### Fixed

- Loose minimum version of rich causing conflicts.

## 0.31.2

### Added

- Add the method `get_server_default`.
- Add `get_columns_nullable`, `get_server_default` and `customize_default_for_server_default` to factory
  overwritable methods.

### Changed

- `server_default` is not extracted anymore by `ColumnDefinitionModel`. Use `get_server_default` instead.
- Lazy evaluate the environment variable for the settings import. This relaxes the restraints on the import order.
  You can e.g. import edgy settings before adjusting `EDGY_SETTINGS_MODULE` as long as you don't access the settings object.
- Don't call `evaluate_settings_once_ready` during init of Registry anymore.


### Removed

- Remove the abstract method `customize_default_for_server_default` from BaseFieldType.

### Fixed

- Fix potential too early import of settings because of the auto computation of server_defaults.

### Breaking

When creating a custom field providing get_columns and
relying on the extraction of server defaults from field, you may need to update the code to use `get_server_default`.

## 0.31.1

### Fixed

- Fix and test QuerySet caching.
- Fix potential hang in `get_metadata_of_all_schemes` with `force_rollback` active.

## 0.31.0

### Added

- Add the ChoiceField alternative CharChoiceField.
- `model_instance` parameter for *_save, *_update signals.

### Changed

- Cleanup the callback interface:
  - The instances are only passed via ContextVars.
  - `force_insert` is by `is_update` replaced.
  - Delete uses now *_INSTANCE ContextVars.
- Split `delete` in `delete` (only used for direct calls) and `raw_delete` for better customizations.
- Split `save` in `save` (only used for direct calls) and `real_save` for better customizations.
- Remove internal only parameter `remove_referenced_call` from delete (but not from raw_delete).
- Change the `remove_referenced_call` to also accept strings, which are the fields from which the deletion originates from.
- Virtual cascade and model based deletions doesn't trigger delete signals anymore (except if `__deletion_with_signals__=True` is set).
- `QuerySet.create` passes now the QuerySet instance as `CURRENT_INSTANCE`.
- `QuerySet.create` passes now the QuerySet instance as signal parameter instance.

### Fixed

- `QuerySet.create` passed the model instance as `CURRENT_INSTANCE`.
- Virtual cascade and model based deletions doesn't trigger delete signals anymore.
- Fix spurious iterate bug in `bulk_get_or_create`, triggered in `edgy-guardian`.
- Fix wrong signal sender class for proxy models.

### Breaking

- For authors of custom fields: the interface of the async callback hooks changed:
  - The instances are only passed via ContextVars.
  - `force_insert` is by `is_update` replaced.
  - Delete callbacks use now *_INSTANCE ContextVars.
- When you overwrote the `delete` method of a model, you probably want to overwrite now `raw_delete`.
- When you overwrote the `save` method of a model, you probably want to overwrite now `real_save`.
- `delete` losses its internal only parameter `remove_referenced_call`.
- When using the pre_save/post_save signal, you might want to use the `model_instance` parameter instead of the `instance`
  parameter. We pass down `QuerySet`s now in create.

## 0.30.1

### Changed

- Split from Page and Paginator BasePaginator and BasePage.
- Add fields next_page, previous_page, current_page to Page.
- Add field current_cursor to CursorPage.
- Make specifying all of the page attributes mandatory.

### Fixed

- Fix and improve pagination examples.

## 0.30.0

### Added

- Add optimized pagination for `QuerySet`.

### Changed

- Internal cleanup how the current row is passed in QuerySet.
- Optimize `reverse` method of QuerySet. Now it reuses a potential available cache.
- `build_pknames` and `build_pkcolumns` return their result instead of setting it automatically.
- Introduce `_edgy_namespace` for edgy related attributes.
- Use `_edgy_namespace` for managers.

### Fixed

- FieldFile did use potential heavily blocking sync API in async code paths.
- `reverse` when no order_by was set.
- Serialization fixes for newer pydantic versions (>=2.11).
- Private attributes handling.

## 0.29.0

### Added

- Convert for most fields defaults to server_default to ease migrations. There are some exceptions.
- Add the setting `allow_auto_compute_server_defaults` which allows to disable the automatic generation of server defaults.
- `pre_migrate` and `post_migrate` signals.

### Changed

- `get_default_value` is now also overwritable by factories.
- The undocumented default of `BooleanField` of `False` is removed.
- The signal receiver functions receive more parameters.

### Fixed

- JSONField `default` is deepcopied to prevent accidental modifications of the default.
  There is no need anymore to provide a lambda.
- `pre_update` and `post_update` is not called anymore when calling save and the update path is executed.
- `apply_default_force_nullable_fields` could run into transaction problems.
- `bulk_update` and `bulk_create` optimizations and small fixes.
- `pre_update` and `post_update` are now received when using a QuerySet.
- Allow prefixing column names in CompositeField via `prefix_column_name` parameter.

### Breaking

- The undocumented default of `BooleanField` of `False` is removed.
- Fields compute now `server_default`s for a set default. This can be turned off via the `allow_auto_compute_server_defaults` setting.


## 0.28.2

### Fixed

- Missing `message` parameter passing in migrate command after refactory.

## 0.28.1

### Changed

- `hash_names` has now two prefix parameters: `inner_prefix`, `outer_prefix`.

### Fixed

- `hash_names` with unique_together incorrectly fed the `uc` prefix into the hasher. This makes the names unidentificatable.
- `BooleanField` logic for automic migrations works by using server_default.

## 0.28.0

### Added

- `null-field` or `nf` parameter for makemigrations/revision.
- Add `FORCE_FIELDS_NULLABLE` ContextVar.
- Add `CURRENT_FIELD_CONTEXT` ContextVar.
- Add automigrations (migrations capsuled in Registry).

### Changed

- The default migration templates allow now to use complex defaults for migrations.
- Fields must use get_columns_nullable instead of ColumnDefinitionModel null. for determining if the columns should be nullable.
- For model `save` and `update` the values can be callables which are evaluated.
- Streamline ContentTypeField in using a parameter-less default function. Use `CURRENT_FIELD_CONTEXT` ContextVar field for referencing the owner.
- Fail when specifying a server_default for ForeignKey, ManyToMany, FileField, ImageField. This is not possible.
- Internals: _insert and _update have now a different signature.

### Fixed

- ForeignKeys aren't required to be saved models when passed.
- Cli command revision takes now also the arg argument.
- Revisioning works now with relative revisions with - (e.g. -2).
- Downgrades are now possible with unique_together. Build a constraint name from the fields.
- `is_partial` was incorrectly set to always `False` for the model.save update path.
- FileFields could have make problems when migrating.
- Differing ruff versions and rules between `hatch fmt` and `pre-commit`.

## 0.27.4

### Changed

- Use `orjson` instead of json for [bulk_get_or_create](./queries/queries.md#bulk-get-or-create).

## 0.27.3

### Added

- [bulk_get_or_create](./queries/queries.md#bulk-get-or-create) to queryset allowing to bulk inserting or getting existing objects.

### Fixed

- BooleanField typing. Thanks to Izcarmt95.

## 0.27.2

### Changed

- Edgy now allows inheritance of `unique_together` and `indexes` from abstract classes.

### Fixed

- Typo in `BaseContentTypeField` from `BaseContentTypeFieldField`.

## 0.27.1

### Added

- `SubFactory` in the model factory helpers allowing to import ModelFactory objects from
  other parts of the codebase and apply them directly as dependencies.
- New `template` to `edgy init` migrations for [sequencial](./migrations/migrations.md#templates) migration file names.
- Sequences like calls for ModelFactory.
- `context` as new parameter to the Marshalls.

### Changed

- The faker argument was switched out to `context`. The `context` parameter however behaves like a faker instance.

### Fixed

- `exclude_autoincrement` argument applies now also for the sub-factories. Previously we would have need to provide the parameters.

## 0.27.0

### Changed

- Added a new table naming schema for through models of ManyToMany fields. This requires however setting
  an explicit table naming schema via the `through_tablename` parameter.
- When `through_tablename` is a string, it is formatted with the field injected as field in the context.

### Fixed

- Multiple ManyFields from the same model to the same target model. Note: this is unrelated to `related_name`, setting the
  the `related_name` would not help.

### BREAKING

For now ManyToMany fields **must** explicitly have a `through_tablename` parameter in which
the table naming schema for the through model is selected.
For existing ManyToMany fields you should pass `edgy.OLD_M2M_NAMING"` so migrations doesn't drop the tables,
for new ManyToMany fields `edgy.NEW_M2M_NAMING"` which prevents clashes of through model names.
You may can also rename the through model table via migration and use the `edgy.NEW_M2M_NAMING"`
or simply use a non-empty string for the `through_tablename` parameter.

## 0.26.1

### Added

- Add PGArrayField.
- Add `build_and_save(...)` build variant to ModelFactory.
- Add `build(save=True)` to ModelFactory.

### Changed

- Reorganize fields. Make more lazy.
- Make models, querysets imports in `__init__.py` lazy so circular dependency errors arise no more.
- Change in ModelFactory the default of `exclude_autoincrement` from `False` to `True`.
  There is a strong demand in having save ready models.

## 0.26.0

### Added

- `__drop_extra_kwargs__` parameter for Models which drops extra kwargs instead passing down. Required for mashalling StrictModel.
- `reference_select` parameter in QuerySet.
- `extra_select` parameter in QuerySet for creating extra select clauses which can be referenced.
- `ref_foreign_key_fields` in meta.

### Changed

- Model allows now like ReflectModel arbitary arguments. Required for `reference_select`.
- Use a partly copied model as ProxyModel. This ensures that the logic of ReflectField still works.

### Fixed

- Cleanup of event-loops and threads in run_sync.
- Fix running shell with auto reflected models.
- Fix `DatabaseNotConnectedWarning` in shell.
- Usage of StrictModels in Mashalls.
- Different autoincrement field in Marshalls than `id`.
- Fix Marshall required check.
- Fix ReflectModel with exclude_secrets.
- Fix non-edgy-fields were stripped instead kept.
- Allow ComputedFields being part of a serialization.

## 0.25.1

### Added

- Add `exclude_autoincrement` parameter/class attribute to ModelFactory.
- Add `build_values` method to ModelFactory. It can be used to extract the values without a model.
- Make Registry initialization compatible with sync contexts via `with_async_env(loop=None)` method.
- `run_sync` has now an optional loop parameter.

### Changed

- The Relation mappings doesn't set the autoincrement id anymore.
- Relationship fields of auto generated ModelFactories of ForeignKey, ... are now excluded when not parametrized.
  This way large trees are avoided.
- Reduce the amount of generated related models to max 10 by default.
- Make `to_factory_field` and `to_list_factory_field` a method instead a classmethod.
  Otherwise they are quite limited.
- `to_list_factory_field` honors the min and max parameter specified by parameters.
  It defaults however to the provided min and max parameters.
- RefForeignKey has now an extra subclass of BaseField. This way the exclusion of works reliable.
- `run_sync` reuses idling loops.
- `run_sync` uses the loop set by the Registry contextmanager `with_async_env`.

### Fixed

- ModelFactory was prone to run in infinite recursions.
- The RefForeignKey field was not working correctly.


## 0.25.0

### Added

- Add `testing.factory.ModelFactory`.
- ManyToManyField `create_through_model` method allows now the keyword only argument `replace_related_field`.
- `add_to_registry` and models have now an additional keyword-only argument `on_conflict` for controlling what happens when a same named model already exists.
  For models this can be passed : `class Foo(edgy.Model, on_conflict="keep"): ...`.
- Passing a tuple or list of types to `replace_related_field` is now allowed.
- Add `through_registry` to ManyToMany.
- Add `no_copy` to models MetaInfo.
- Add `ModelCollisionError` exception.
- Add keyword only hook function `real_add_to_registry`. It can be used to customize the `add_to_registry` behaviour.
- Add `__no_load_trigger_attrs__` to edgy base model to prevent some attrs from causing a deferred load.

### Changed

- `create_edgy_model` has now `__type_kwargs__` which contains a dict of keyword arguments provided to `__new__` of type.
- RelatedField uses now `no_copy`.
- `add_to_registry` returns the type which was actually added to registry instead of None.
- Through models use now `no_copy` when autogenerated. This way they don't land in copied registries but are autogenerated again.
- Instead of silent replacing models with the same `__name__` now an error is raised.
- `skip_registry` has now also an allowed literal value: `"allow_search"`. It enables the search of the registry but doesn't register the model.
- Move `testclient` to `testing` but keep a forward reference.
- Change the default for ManyToMany `embed_through` from "" to `False` which affected traversing ManyToMany.
- Better protect secrets from leaking. Prevent load when accessing a secret field or column.

### Fixed

- Copying registries and models is working now.
- Fix deleting (clearing cache) of BaseForeignKey target.
- Creating two models with the same name did lead to silent replacements.
- Invalidating caused schema errors.
- ManyToMany and ForeignKey fields didn't worked when referencing tenant models.
- ManyToMany fields didn't worked when specified on tenant models.
- Fix transaction method to work on instance and class.
- Fix missing file conversion in File. Move from ContentFile.
- Fix mypy crashing after the cache was build (cause ChoiceField annotation).
- Fix handling unknown fields via the generic_field.
- Sanify default for embed_through which affected traversing ManyToMany.
  It defaulted to the backward compatible "" which requires the user to traverse the m2m model first.
- Prevent fully initialized models from triggering a deferred load.
- Prevent accessing excluded secrets from triggering a deferred load.

### BREAKING

- Instead of silent replacing models with the same `__name__` now an error is raised.
- The return value of `add_to_registry` changed. If you customize the function you need to return now the actual model added to the registry.
- The default for ManyToMany `embed_through` changed from "" to `False` which affected traversing ManyToMany. For keeping the old behaviour pass:
  `embed_through=""`.
- Accessing field values excluded by exclude_secrets doesn't trigger an implicit load anymore.

## 0.24.2

### Fixed

- Try harder to avoid circular imports when providing settings with edgy references.

## 0.24.1

### Fixed

- Comparation of a model with non-models.

## 0.24.0

### Added

- True multi-database migrations.
  You may need to rework your migrations in case you want to use it.
- Generalized `hash_to_identifier` function.
- `get_name` function on `metadata_by_url` dict.
- Differing databases can be passed via `database` attribute on models.
- `create` method on relations (reverse side of ForeignKeys and both sides of ManyToMany).

### Changed

- Breaking: empty names are not allowed anymore for extra. This includes names consisting of spaces.

### Fixed

- ForeignKey remote check failed for objects with different database but same registry.

## 0.23.3

### Fixed

- Version number mismatch.

## 0.23.1 & 0.23.2

### Fixed

- Docs were broken.
- Autodetection of the instance was broken when a directory containing dots is in the folder.
- Fix compatibility with pydantic 2.10.

## 0.23.0

### Added

- Extension support via Monkay.

### Changed

- Rework edgy to use Monkay.
- Imports are now lazy.
- Rework the migrate and shell system to simply use Monkay instance.
- Replace `get_registry_copy` by `get_migration_prepared_registry`.
- Breaking: migration configuration takes place in settings.
- Breaking: EdgyExtra and Migrate are replaced by `edgy.Instance` but are still available.
- Breaking: EdgyExtra is provided by the also obsolete Migrate.
- Breaking: `model_apps` is replaced by `preloads` but still available during the migration time.
- Breaking:
  An automatic registration is assumed. See [Connection](connection.md) for examples.
- Breaking: `--app` or `EDGY_DEFAULT_APP` must point to a module which does the self-registration not an app instance anymore.
- Deprecate `edgy.conf.enums.EnvironmentType`. Esmeralds `EnvironmentType` or an own definition should be used instead.
- Deprecate `edgy.conf.module_import.import_string`. Use `monkay.load` instead.

### Fixed

- Migrations with ManyToMany fields are broken.
- `get_engine_url_and_metadata` was broken for some operations (thanks @kokoserver).
- IPAddressField was not exposed as edgy.IPAddressField.

### Removed

- `edgy.conf.functional`. It was only used for configuration and is now superseeded by Monkay.

### Contributors

Thanks a lot to @kokoserver. He provided a *lot* of valuable bug reports and PRs.


## 0.22.0

### Added

- Global constraints via meta.
- Allow functional indexes.
- Expose further parameters for UniqueConstraints.
- `no_copy` attribute for fields.

### Changes

- Breaking: Factories pass now the kwargs as dict to get_pydantic_type, get_column_type, get_constraints.
  This allows now modifying the arguments passed down to the field.
- Breaking: init_fields_mapping doesn't initializes the field stats anymore.
- Breaking: model rebuilds are executed lazily when calling init_fields_mapping not when assigning fields manually anymore.

### Fixed

- Indexes and unique_together worked only for fields with columns of the same name.
- MigrateConfig has no get_registry_copy.
- Migrations have duplicate fks and crash.
- ContentTypes were not copyable.
- VirtualCascade was not automatically enabled.
- Improve lazyness by splitting in two variable sets.

## 0.21.2

### Added

- PlaceholderField.
- StrictModel which forbids extra attributes.

### Changed

- Validate on assignment is enabled.
- IPAddressField uses now pydantic validation and a simplified TypeDecorator.
- URLField is now validated.

### Fixed

- Pydantic validators are fixed. Field based ones as well as model based ones.
- `__dict__` was wiped out when intializing a model.

## 0.21.1

### Changed

- Breaking: from_kwargs doesn't require model or table anymore. It is simply ignored.

### Fixed

- Q, and_, or_ support now complex kwargs like querysets.
- Failure querying when using proxy model table and kwargs.
- Proxy and main model use now the same tables.
  This could have been a problem when filtering against table columns of the proxy table in a query from the main table.
- Queries operate now always on the main model not the proxy model.
- Stacklevel of performance warning was wrong.

## 0.21.0

### Added

- Allow multi schema and database migrations.
- `metadata_by_url` dictionary.

### Changed

- `metadata` of `registry` is now `metadata_by_name`.
- `hash_tablekey` uses a faster hash function.
- Migrate object provides now a function for getting a suitable registry copy for migrations.
- Change license to bsd-3.
- Proper deprecate unset autoincrement when using it with primary key. The behavior is already deprecated in the documentation.

### Fixed

- `Migrate` executed `refresh_metadata` everytime causing reflected models to vanish.
- Fix edgy wrapping esmerald with the asgi helper causing esmeralds cli to disappear.

## 0.20.0

### Added

- Add DurationField.
- Allow passing `max_digits` to FloatField.
- Add `local_or` function to QuerySets.

### Changed

- Only the main table of a queryset is queryable via `model_class.columns.foo == foo`. Select related models have now an unique name for their path.
  The name can be retrieved via `tables_and_models` or using `f"{hash_tablekey(...)}_{column}"`.
- Breaking: Alter tables_and_models to use the prefix as key with '' for the maintable and model.
- Breaking: Functions passed to filter functions reveive now a second positional parameter `tables_and_models`.
- `build_where_clause` conditionally uses a subquery.
- Rename QueryType to QuerySetType. The old name stays as an alias.
- The debug property of QuerySet named `sql` inserts now the blanks and uses the dialect.

### Fixed

- Triggering load on non-existent field when reflecting.
- InspectDB mapping was incorrect.
- Fix query edge cases.
- Fix using related queries with update/delete.


## 0.19.1

### Fixed

- Migration issues with ManyToMany fields.
- Wrong UUIDField type.
- Passing options from Migrate to the alembic context.

## 0.19.0

### Added

- New `SET_DEFAULT`, and `PROTECT` to `on_delete` in the ForeignKey.
- New `through_tablename` parameter for ManyToMany.

### Removed

- `__db_model__` is removed. Replaced by registry = False.

### Changed

- Allow setting registry = False, for disabling retrieving the registry from parents.
- Removed unecessary warning for ManyToMany.
- Add warnings for problematic combinations in ForeignKey.
- Make QuerySet nearly keyword only and deprecate keywords not matching function names.
- Clone QuerySet via `__init__`.
- Make select_related variadic and deprecate former call taking a Sequence.
- Improved QuerySet caching.

### Fixed

- Multi-column fields honor now `column_name`. This allows special characters in model names.

## 0.18.1

### Changed

- Cleanup Model inheritance: Database related operations are put into a mixin. The customized metaclass is moved from EdgyBaseModel to `edgy.Model` as well as some db related ClassVars.
- `multi_related` is now a set containing tuples (from_fk, to_fk). This can be used to identify fields used by ManyToMany fields.
- Deprecate `is_multi`.
- Deprecate `parents`. There are no users, it was undocumented and uses are limited.

### Fixed

- Non-abstract through-models wouldn't be marked as many to many relations.
- Issues related with the Edgy shell initialization.

## 0.18.0

### Added

- ComputedField.
- Permission template.
- `reverse_clean` for ForeignKeys.
- Expanded filter methods of querysets (can pass now dict and querysets).
- Properly scoped `with_tenant` and `with_schema`.

### Changed

- Managers use now instance attributes (database, schema).
- Expose `as_select` instead of `raw_query`.
- `model_fields` contain now the fields so we can actually use the pydantic magic.
- BREAKING: deprecate `set_tenant` and remove manager hack. This way the tenant scope could leak. Use `with_tenant` instead.

### Fixed

- `select_related` works across ManyToMany fields.
- `select_related` couldn't handle multiple pathes to the same table.
- `select_related` would remove valid model instances because of non-existent related objects.
- Fix identifying clashing column names in joins, so every model gets its right parameters.
- Dependency tracking for join, so it doesn't depend on the order of `select_related`.
- `select_related` entries work in any order and don't overwrite each other.
-`only` and `defer` work on `select_related`.
- Autogenerated `id` wasn't added in model_dump.
- Tenants worked only till the first query.

### Breaking changes (upgrade path)

``` python
set_tenant("foo")
```

Becomes now

``` python
with with_tenant("foo"):
  ...
```


``` python
activate_schema("foo")
...
deactivate_schema()
```

Becomes now

``` python
with with_schema("foo"):
  ...
```

## 0.17.4

### Fixed

- `model_dump_json` returns right result.
- `show_pk=False` can now be used to disable the inclusion of pk fields regardless of `__show_pk__`.
- `__setattr__` is called after insert/update. We have transform_input already.

## 0.17.3

### Fixed

- Lazy ManyToMany fields.

## 0.17.2

### Added

- `build_where_clause` method in QuerySet for easing the integration in raw SQLAlchemy queries.

### Fixed

- `update` and `delete` methods of QuerySet did ignore or clauses.
- Fixed ManyToMany fields not able to use their owner Model as target.
- Fixed makemigration failing with foreignkeys when using model_apps.

## 0.17.1

### Added

- `CURRENT_MODEL_INSTANCE` ContextVariable which always point to a model instance.

### Fixed

- Under circumstances it was possible for the assigned database attribute to appear as value.
- Typings of some (class) properties are now correctly detected.
- FileFields doesn't need an explicit `to_file` call assignment anymore to work with revisions. This restriction was lifted.
- Execute database operation of `bulk_update` in right scope.

## 0.17.0

### Added

- Support for querying across multiple databases.
- Support for passing functions as clauses or keyword parameters.
- Support for autocreated reflection objects by pattern matching.
- Added some context variables for `extract_column_values` and `transform_input`:
  - `CURRENT_PHASE`: allows retrieving the current context in which it was executed.
  - `EXPLICIT_SPECIFIED_VALUES`: when set, it returns a set of the keys from the explicitly specified values.

### Changed

- `crawl_relationship` has a slightly changed interface: it has `cross_db_remainder` as kwarg for callbacks and in the result.
  Also it doesn't raise NotImplementedError anymore when detecting a crossdb situation.
- `is_cross_db` optionally gets a database as parameter and compares the databases instead of registries.
- Relax fields parameter requirements for values/values_list.
- More lazy meta/metadata.
- `database` attribute of models is used for queries instead of the main database of the registry.
- We use more metaclass kwarg arguments.
- Switch to python >= 3.9.
- Rename internal `_is_init` of MetaInfo to `_fields_are_initialized`.
- `phase` argument is shifted to `CURRENT_PHASE` context_var. If you rely on the correct phase you need to use it instead.
- `extract_column_values` provides now also a `CURRENT_PHASE` environment.
- `is_update` argument of `get_defaults` is now replaced by `CURRENT_PHASE` too. It is way more accurate.
- Deprecate `force_save` kwarg of save in favor of `force_insert`. This is way more precise.
- `post_save_callback` receives now also the `force_insert` parameter.

### Fixed

- Fix ForeignKey not None but empty hull under some conditions.
- Fix DecimalField requiring `max_digits`.

## 0.16.0

### Added

- ASGI, async context manager support to connect/disconnect multiple dbs at once.
- `create_all`/`drop_all`, `create_schema`/`drop_schema` are now capable of initializing dbs in extra.
- Add `transaction` helper to Model and QuerySet.
- Allow copying models properly.
- Allow None as default.

### Changed

- Unify `using` to allow setting schema and database via keyword arguments and deprecate both former calls.

### Fixed

- Esmerald typing issues.
- Migration metadata was not completely initialized which caused problems.
- Foreign keys None/null handling was inconsistent. Now we have a None for unset foreign keys.

## 0.15.0

### Added

- FileField and File handling.
- ImageField stub (more is comming soon)
- `stage` method in relations.
- ModelRefs passed as normal positional arguments are automatically staged.
- ContentType was added.
- Proper callback support was added.
- `remove_referenced` parameter for ForeignKeys was added.
- Virtual `CASCADE` deletion is now used for ForeignKeys without constraint.

### Changed

- Breaking: ModelReferences use now the related name instead of the model name.
- Breaking: Field Factories pass now keyword arguments as positional dictionary. This way keyword arguments manipulations in validate are possible.
  This way it can be distinguished between multiple foreign keys to the same model and self-references are possible.
- `model_references` are superseeded by `post_save_fields` in meta.
- ModelParser mixin is gone. Use the classmethod `extract_column_values` instead.
- edgy_settr is not used internally anymore (circular imports).
- `modify_input` receives now an argument phase.
- `foreign_key_fields` is now a frozenset.
- Switch away from nest_asyncio.
- All sqlalchemy operators are now accessable. The setting for them is gone.

### Fixed

- Factory overwrites can now access owner.
- Foreign keys to reflected models.
- Handling to string references not in registry loaded yet.
- Timezone aware Datetime saved in timezone unaware database columns.

## 0.14.1

### Changed

- Bump dependency of databasez.

### Fixed

- Fix load_recursive.

## 0.14.0

## Added

- Cache per queryset.
- Expose raw_query for getting a raw sqlalchemy query.
- Expose control for used batch size.
- Add load_recursive for initializing a nested model structure.


### Changed

- Server defaults don't trigger load after saving.
- Less nested run_sync calls.
- Alter queryset methods to contain useful arguments, instead of ignoring kwargs.
- Replace QuerysetProtocol by abstract base type.

### Fixed

- `get_or_none` was not abidding embed_parent.
- Correctly apply filters on relations.
- `last` and `first` don't fail without id column anymore.

### Removed

- Unused and broken debug arguments, like raw_query on model classes.
- Remove run_query of models.

## 0.13.1

## Added

- Testclient can be configured via environment variables.

### Fixed

- Compatibility with newer databasez releases (>0.9).

## 0.13.0

### Added

- `default_timezone`, `force_timezone`, `remove_timezone` for DateTimeField.
- `default_timezone`, `force_timezone` for DateField.
- Add attribute `inject_default_on_partial_update`.
- Allow factories overwriting field methods.
- Deep embedding via embed_parent possible.
- Support for nearly all async sqlalchemy drivers plus more from databasez.

### Changed

- `get_default_values` has now an extra keyword argument `is_update`
- `meta.fields_mapping` was renamed to `meta.fields`.-
- Factories have now different named configuration variables.
- Refactoring of fields and models:
  - BaseModelType and BaseFieldType are now added and should be used for typings.
  - `get_column` works now via extractor.
  - Renamed internals.
  - Splitted model_references and column values extraction.
- Comparisons of models use now only primary keys.
- Deprecate on model forwards signals, fields. Use now meta.signals, meta.fields.

### Removed

- execsync (nearly no uses).
- DateParser mixin (superseeded by sqlalchemy's logic).

### Fixed

- `auto_now` and `auto_now_add` now also work for date fields.
- `BinaryField` had a wrong type.
- Metaclasses with keyword arguments are now possible.
- Relaxed Prefetching, tables can now appear multiple times.
- `select_related` now correctly filters columns.

## 0.12.0

### Added

- Allow multiple ForeignKeys with the same related_name in one model.
- Support ForeignKeys on multiple columns.
- Allow selecting columns for ForeignKeys.
- Allow skipping creating a ForeignKeyConstraint.
- Add ExcludeField for masking fields in submodels.
- ManyToMany fields pass unique through to target foreignkey.
- Add ConditionalRedirect constant for CompositeField.
- Embeddables via CompositeField. See [Embedding](./embedding.md)
- Add ForeignKeyFactory, a factory with presets for building foreign keys.
- Multiple primary keys and names different from "id" are possible now.
- Add inherit flag for Manager, BaseFields and Models (when used as an embeddable). It is used for controlling the inheritance.
- Managers are now instance aware. You can customize the instance and they can react. They are also shallow copied for every class and instance.
- Improved Relations (reverse side of ForeignKeys and forward side of Many2Many). Have now add and remove methods and work like RefForeignKey (you can just specify an Array with assignment targets and they will be added).
- Allow skip building reverse RelatedFields for ForeignKeys with `related_name=False`.
- `pkcolumns` attribute of models (contains all found primary key columns).
- Some new methods on BaseField:
  - `embed_field`: for controlling embedding a field in an CompositeField.
  - `get_column_names`: helper function for retrieving the column names of a field.
- Add RelationshipField for traversable fields.

### Changed

- ForeignKeys use now global constraints and indexes.
- Breaking: clean has now the argument to_query. See [Custom Fields](./fields/index.md#custom-fields).
- Breaking: ManyToMany doesn't have a RelatedField on owner anymore and uses proxying. See [ManyToMany](./fields/index.md#manytomany).
- Breaking: use singular related_name for unique ForeignKeys (or OneToOne). See [related_name](./queries/related-name.md)
- MetaInfo (meta) is now partly lazy.
- `pk` is now a PKField (a variant of the BaseCompositeField).
- `clean` and `to_columns` of BaseField do return empty objects instead of raising NotImplementedError.
- Major refactory of ForeignKeys, move logic for single ForeignKeys to subclass.
- Move FieldFactory and ForeignKeyFieldFactory to factories.
- Remove superfluous BaseOneToOneKeyField. Merged into BaseForeignKeyField.
- Remove unused attributes of MetaInfo and added some lazy evaluations for fields.

#### Breaking

- Prefetch traversal of foreign keys uses now the foreign key name. For the traversal of RelatedFields everything stays the same.

## 0.11.1

### Added

- [create_schema](./tenancy/edgy.md#the-schema-creation) allowing a dynamic and programatically
way of creating schemas in the database.

### Changed

- Updated `reflection` from `edgy.ReflectModel` to use the internal database session and avoid
deadlocks.
- Internal cleaning for tenancy.

## 0.11.0

### Added

- Support for [Marshall](./marshalls.md) allowing custom serialization of an Edgy model by [@tarsil](https://github.com/tarsil).
- Support for the new [CompositeField](./fields/index.md#compositefield) enhancing the ability of
having multiple primary keys (or composed keys) in an Edgy model by [@devkral](https://github.com/devkral).
- Support for the `Q` queryset clause by [@devkral](https://github.com/devkral).

### Changed

- Cleaned up `FieldFactory` internals by [@devkral](https://github.com/devkral).
- `pyproject.toml` definitions by [@devkral](https://github.com/devkral).
- Internal Edgy `model_dump` covering internals of Edgy and corner cases of Pydantic for compatibility reasons by [@devkral](https://github.com/devkral).

### Fixed

- Typos in `is_primary` key attribute by [@devkral](https://github.com/devkral).
- InspectDB when provided with a `schema` name was not using it in the registry.

## 0.10.1

### Added

- Support for `list` and `tuples` as a type for [model_apps](./migrations/migrations.md).

## 0.10.0

### Added

- Support for `model_apps` inside the `Migrate` object allowing
global discovery by application. This will make sure all apps will be properly
inspected.
- Add documentation about the new [model_apps](./migrations/migrations.md)

### Changed

- Upgrade internal requirements.

## 0.9.2

### Changed

- Update internal anyio dependency.

## 0.9.1

### Changed

- Upgrade internal requirements.

### Fixed

- `auto_now` and `auto_now_add` on `save()` and `update()` wasn't only updating the
field with `auto_now`.
- Extraction of the default field for `date` and `datetime`.

## 0.9.0

### Added

- Tenancy for internal `proxy_model` validation added.
- Support for ManyToMany to accept strings to the `to` attribute.
- Allowing querying inner foreign keys without needing to use `select_related` or `load`

### Changed

- Increased maximum of 63 characters the name of the index/unique.
- ModelRow now contains private methods.
- Updated documentation with missing [select_related](./queries/queries.md#load-the-foreign-keys-beforehand-with-select-related).
- Updated documentation for [access of data via foreign keys](./relationships.md#access-the-foreign-key-values-directly-from-the-model).

### Fixed

- When generating a many to many through model, the maximum length is enforced to be 63 characters.
- Allow `ManyToMany` to also accept a string as a parameter for the `to`.
- Object discovery for intellisense in any IDE.

## 0.8.1

### Added

- Added new experimental `activate_schema` for tenant models using the `using` queryset operator.

### Fixed

- Multiple join tables were not generating the complete join statement when using `select_related`.
- Fixed metaclass for TenantMixin making sure all the queries are correctly pointing
to the right tenant.

## 0.8.0

### Added

- Support for `sync` queries. This will enable Edgy to run in blocking frameworks like
Flask, bottle or any other by using the newly added [run_sync](./queries/queries.md#blocking-queries). [#60](https://github.com/dymmond/edgy/pull/60).

### Fixed

- Fixed multi tenancy from contrib. [#58](https://github.com/dymmond/edgy/pull/58).
- Fixed `using` where schema name was raising a not found reference for foreign key
when querying the tenant. [#58](https://github.com/dymmond/edgy/pull/58).
- Fixed `exclude_secrets` when querying models with foreign keys. [#59](https://github.com/dymmond/edgy/pull/59).

### 0.7.1

### Fixed

- `exclude_secrets` quick patch for the way it can recursively understand the model fields when
filtering the query.

## 0.7.0

### Added

- Support for [`or_`, `and_` and `not_`](./queries/queries.md#edgy-style) for SQLAlchemy style queries and Edgy syntax sugar queries.
- Support for [`secrets`](./queries/secrets.md) field and queryset allowing to query the fields that are not marked as `secret` directly.

### Changed

- Updated internal support for `databasez` 0.7.0 and this fixes the URL parsing errors for complex passwords
caused by the `urlsplit`.

## 0.6.0

### Changed

- `inspectdb` is now handled by an independent isolated called `InspectDB`.

### Fixed

- `server_default` does not raise a `FieldValidationError`.
- `server_default` added as validation for nullable.
- `null` was not being applied properly from the newly added `server_default`.

!!! Warning
	This could impact your migrations, so the advise would be to generate a new migration
	after upgrading to the new version of Edgy to make sure the database reflects the proper
	nullables/non-nullable fields.

## 0.5.2

### Changed

- Add [API Reference](http://edgy.tarsild.io/references/).
- Update base requirements.

### Fixed

- `Database` object docstring.


## 0.5.1

### Changed

- Base metaclass that is now generating the initial annotations for validations.
- Update Pydantic version.
- Update documentation to reflect the new fixed issues.

### Fixed

- Raise `ImproperlyConfigured` for managers that are not typed as `ClassVar` avoiding
maximum recursion error. [#19](https://github.com/dymmond/edgy/pull/39).

## 0.5.0

### Added

- Added support for Python 3.12.

### Changed

- Update base requirements.

### Fixed

- Removed copy of docs folder
- `minimum_length` to `min_length`.
- `values_list()` to implement the `queryset.clone()`.
- Fixed `.json()` to `model_dump_json()`.

## 0.4.0

### Added

- New [Prefetch](./queries/prefetch.md) support allowing to simultaneously load nested data onto models.
- New [Signal](./signals.md) support allowing to "listen" to model events upon actions being triggered.

### Changed

- Updated pydantic and alembic

## 0.3.1

### Fix

- `DecimalField` definition raising unknown constraint `max_digits`.
-  DeclarativeModel generating internal mappings names was breaking for class objects.

## 0.3.0

### Added

- **Multi tenancy support** by updating the registry and allowing to create the multi schema.
- Add new `using(schema=...)` and `using_with_db(database=..., schema=...)` to querysets.
- Add support for `create_schema` and `drop_schema` via registry.
- Add support to `get_default_schema` from the `registry.schema`.
- Documentation for [tenancy](./tenancy/edgy.md).
- Improved the documentation for [schemas](./registry.md#schemas).
- Added a new parameter `extra` to registry allowing to pass a Dict like object containing more database connections. This is an alternative to the registries.
- Improved documentation for [registry](./registry.md#extra) explaining how to use the extra parameters.
and query them.

### Changed

- Update the `build` for `Model` and `ReflectModel` to allow passing the schema.

### Fixed

- Registry `metaclass` wasn't reflecting 100% the schema being passed into the metadata and therefore, querying the database public schema.

## 0.2.0

### Added

- [RefForeignKey](./reference-foreignkey.md). A model reference where it can create sub objects from the main object directly.
- Performance enhancements in general.

### Changed

- The way fields are evaluated and caching for the `__model_reference__` fields.

### Fixed

- Improved performance of the `__proxy_model__` by caching.

## 0.1.0

This is the initial release of Edgy.

### Key features

* **Model inheritance** - For those cases where you don't want to repeat yourself while maintaining
integrity of the models.
* **Abstract classes** - That's right! Sometimes you simply want a model that holds common fields
that doesn't need to created as a table in the database.
* **Meta classes** - If you are familiar with Django, this is not new to you and Edgy offers this
in the same fashion.
* **Managers** - Versatility at its core, you can have separate managers for your models to optimise
specific queries and querysets at ease.
* **Filters** - Filter by any field you want and need.
* **Model operators** - Classic operations such as `update`, `get`, `get_or_none`, `bulk_create`,
`bulk_update`, `values`, `values_list`, `only`, `defer` and a lot more.
* **Relationships made it easy** - Support for `OneToOne`, `ForeignKey` and `ManyToMany` in the same Django style.
* **Constraints** - Unique constraints through meta fields.
* **Indexes** - Unique indexes through meta fields.
* **Native test client** - We all know how hard it can be to setup that client for those tests you
need so we give you already one.
