---
hide:
  - navigation
---


# Release Notes


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
- Breaking: clean has now the argument to_query. See [Custom Fields](./fields.md#custom-fields).
- Breaking: ManyToMany doesn't have a RelatedField on owner anymore and uses proxying. See [ManyToMany](./fields.md#manytomany).
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
- Support for the new [CompositeField](./fields.md#compositefield) enhancing the ability of
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
