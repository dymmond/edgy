# API Reference

Here lies the API-level documentation for the main classes and objects you use with Edgy.

If you are starting out, begin with the narrative guides first:

* [Edgy](https://edgy.dymmond.com/edgy)
* [Models](../models.md)
* [Queries](../queries/queries.md)
* [Migrations](../migrations/migrations.md)

## Reference Map

Use these pages when you already know what you need and want method/attribute details:

* **Data layer:** `Model`, `ReflectModel`, `Manager`, `QuerySet`
* **Schema and DB:** `Registry`, `Schema`, `Database`
* **Fields:** base field API and relationship fields
* **Signals:** low-level signal type reference

## Typical Lookups

* "How do I switch schema/database in queries?" -> [QuerySet](./queryset.md), [Registry](./registry.md)
* "How do I inspect model behavior and helpers?" -> [Model](./models.md), [ReflectModel](./reflect-model.md)
* "How do field relation parameters behave?" -> [ForeignKey](./foreignkey.md), [ManyToMany](./many-to-many.md), [OneToOne](./one-to-one.md), [RefForeignKey](./reference-foreign-key.md)
