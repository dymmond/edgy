# Inspecting Existing Databases

It's not uncommon for projects to switch ORMs, especially during the initial discovery phase when the ideal technology stack is being determined. While the SQL database often remains constant, the ORM used to interact with it may change.

Edgy's `inspectdb` command-line tool addresses this scenario by allowing you to read an existing database's schema and generate [Reflected Models](./reflection/reflection.md). This effectively maps your database tables into an **Edgy-compatible syntax**, simplifying the process of working with pre-existing databases.

!!! Tip
    If you're unfamiliar with [Reflected Models](./reflection/reflection.md), taking a moment to review that section will provide valuable context.

## Reflected Models: A Bridge to Existing Databases

When `inspectdb` is executed, it generates [Reflected Models](./reflection/reflection.md). These models differ from standard Edgy models in that they are **not managed by Edgy's migration system](./migrations/migrations.md). However, they function identically to regular [Edgy models](./models.md) in terms of data access and manipulation.

This distinction serves as a **safety measure**. By excluding reflected models from Edgy's migration system, Edgy prevents accidental modifications to your existing database schema.

## How `inspectdb` Works

Using `inspectdb` is straightforward. You can generate reflected models using a database URL.

### Database URL

This is the most common and convenient method. The syntax is as follows:

```shell
edgy inspectdb --database <CONNECTION-STRING> > <NAME-OF-FILE>.py
```

**Example:**

```shell
edgy inspectdb --database "postgres+asyncpg://user:password@localhost:5432/my_db" > models.py
```

This command will generate Edgy reflected models based on the specified database and write them to the `models.py` file. You can then use these models within your Edgy application.

#### `inspectdb` Parameters

To explore the available parameters for `inspectdb`, use the `--help` flag:

```shell
edgy inspectdb --help
```

* **`--schema SCHEMA`:** Specifies the schema to connect to. For example, in MSSQL, `dbo` is commonly used. This parameter is typically used in specific database environments.
* **`--database CONNECTION_STRING`:** Provides the fully qualified connection string to the database. Example: `postgres+asyncpg://user:password@localhost:5432/my_db`.

## Practical Use Cases

* **Migrating to Edgy:** If you're transitioning an existing database-driven application to Edgy, `inspectdb` allows you to quickly generate models for your existing tables.
* **Working with Legacy Databases:** When interacting with legacy databases that weren't initially designed for Edgy, `inspectdb` enables you to seamlessly integrate them.
* **Rapid Prototyping:** During development, `inspectdb` can be used to quickly generate models for existing database schemas, accelerating the prototyping process.

## Key Considerations

* **Data Types:** `inspectdb` attempts to map database data types to the closest Edgy field types. However, manual adjustments may be necessary in some cases.
* **Relationships:** `inspectdb` can infer foreign key relationships between tables. However, complex or non-standard relationships may require manual configuration.
* **Migrations:** Remember that reflected models are not managed by Edgy's migration system. Any schema changes must be made directly to the database.

By using `inspectdb`, you can efficiently bridge the gap between existing databases and Edgy, facilitating seamless integration and simplifying the process of working with pre-existing data.
