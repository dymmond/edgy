# Release Notes

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
intregity of the models.
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
