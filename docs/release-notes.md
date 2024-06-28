---
hide:
  - navigation
---

# Release Notes

## Unreleased

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
  - embed_field: for controlling embedding a field in an CompositeField.
  - get_column_names: helper function for retrieving the column names of a field.
- Add RelationshipField for traversable fields.


### Changed

- Breaking: Prefetch traversal of foreign keys uses now the foreign key name. For the traversal of RelatedFields everything stays the same.
- ForeignKeys use now global constraints and indexes.
- Breaking: clean has now the argument to_query. See [Custom Fields](./fields.md#Custom%20Fields)
- Breaking: ManyToMany doesn't have a RelatedField on owner anymore and uses proxying. See [ManyToMany](./fields.md#ManyToMany)
- Breaking: use singular related_name for unique ForeignKeys (or OneToOne). See [related_name](./queries/related-name.md)
- MetaInfo (meta) is now partly lazy.
- `pk` is now a PKField (a variant of the BaseCompositeField).
- `clean` and `to_columns` of BaseField do return empty objects instead of raising NotImplementedError.
- Major refactory of ForeignKeys, move logic for single ForeignKeys to subclass.
- Move FieldFactory and ForeignKeyFieldFactory to factories.
- Remove superfluous BaseOneToOneKeyField. Merged into BaseForeignKeyField.
- Remove unused attributes of MetaInfo and added some lazy evaluations for fields.

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

- Support for `list` and `tuples` as a type for [model_apps](./migrations/migrations.md#using-the-model_apps).

## 0.10.0

### Added

- Support for `model_apps` inside the `Migrate` object allowing
global discovery by application. This will make sure all apps will be properly
inspected.
- Add documentation about the new [model_apps](./migrations/migrations.md#using-the-model_apps)

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

- Added new experimental [activate_schema](./tenancy/edgy.md#using-with-activate_schema) for tenant models using the `using` queryset operator.

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
