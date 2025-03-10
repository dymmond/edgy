# Migrations

Database migration tools are essential for managing incremental database changes.

Edgy, built on top of SQLAlchemy core, includes a powerful internal migration tool.

This tool simplifies the management of models and their corresponding migrations.

Inspired by Flask-Migrations, Edgy's migration tool is framework-agnostic, making it usable **anywhere**.

## Important

Before proceeding, familiarize yourself with Edgy's application discovery methods.

The following examples will use the `--app` and environment variable approach (see [Discovery](./discovery.md#environment-variables)), but auto-discovery (see [Auto Discovery](./discovery.md#auto-discovery)) is equally valid.

## Project Structure for this Document

For clarity, we'll use the following project structure in our examples:

```shell
.
├── README.md
├── .gitignore
└── myproject
    ├── __init__.py
    ├── apps
    │   ├── __init__.py
    │   └── accounts
    │       ├── __init__.py
    │       ├── tests.py
    │       └── v1
    │           ├── __init__.py
    │           ├── schemas.py
    │           ├── urls.py
    │           └── views.py
    ├── configs
    │   ├── __init__.py
    │   ├── development
    │   │   ├── __init__.py
    │   │   └── settings.py
    │   ├── settings.py
    │   └── testing
    │       ├── __init__.py
    │       └── settings.py
    ├── main.py
    ├── serve.py
    ├── utils.py
    ├── tests
    │   ├── __init__.py
    │   └── test_app.py
    └── urls.py
```

## Migration Object

Edgy requires a `Migration` object to manage migrations consistently and cleanly, similar to Django migrations.

This `Migration` class is framework-independent. Edgy ensures it integrates with any desired framework upon creation.

This flexibility makes Edgy uniquely adaptable to frameworks like Esmerald, Starlette, FastAPI, and Sanic.

```python
from edgy import Instance, monkay

monkay.set_instance(Instance(registry=registry, app=None))
```

### Parameters

The `Instance` object accepts the following parameters:

* **registry**: The model registry. It **must be** an instance of `edgy.Registry` or an `AssertionError` is raised.
* **app**: An optional application instance.

## Migration Settings

Migrations now utilize Edgy settings. Configuration options are located in `edgy/conf/global_settings.py`.

Key settings include:

* `multi_schema` (bool / regex string / regex pattern): (Default: `False`). Enables multi-schema migrations. `True` for all schemas, a regex for specific schemas.
* `ignore_schema_pattern` (None / regex string / regex pattern): (Default: `"information_schema"`). When using multi-schema migrations, ignore schemas matching this regex pattern.
* `migrate_databases` (tuple): (Default: `(None,)`). Specifies databases to migrate.
* `migration_directory` (str): (Default: `"migrations"`). Path to the Alembic migration folder. Overridable per command via `-d` or `--directory` parameter.
* `alembic_ctx_kwargs` (dict): Extra arguments for Alembic. Default:

    ```python
    {
        "compare_type": True,
        "render_as_batch": True,
    }
    ```

### Usage

Using the `Instance` class is straightforward. For advanced usage, see the [LRU cache technique](../tips-and-tricks.md#the-lru-cache) in [Tips and Tricks](../tips-and-tricks.md).

We'll use a `utils.py` file to store database and registry information.

```python title="my_project/utils.py" hl_lines="4-9"
{!> ../docs_src/migrations/lru.py !}
```

This ensures object creation only once.

Now, use the `Migration` object in your application.

#### Using Esmerald

```python title="my_project/main.py" hl_lines="6 36-40 42"
{!> ../docs_src/migrations/migrations.py !}
```

#### Using FastAPI

Edgy's framework-agnostic nature allows its use in FastAPI applications.

```python title="my_project/main.py" hl_lines="6 36 38"
{!> ../docs_src/migrations/fastapi.py !}
```

#### Using Starlette

Similarly, Edgy works with Starlette.

```python title="my_project/main.py" hl_lines="6 35 37"
{!> ../docs_src/migrations/starlette.py !}
```

#### Using Other Frameworks

Edgy's design requires no framework-specific parameters, allowing integration with frameworks like Quart, Ella, or Sanic.

#### Example

Consider an application with the following structure:

```shell
.
├── README.md
├── .gitignore
└── myproject
    ├── __init__.py
    ├── apps
    │   ├── __init__.py
    │   └── accounts
    │       ├── __init__.py
    │       ├── tests.py
    │       ├── models.py
    │       └── v1
    │           ├── __init__.py
    │           ├── schemas.py
    │           ├── urls.py
    │           └── views.py
    ├── configs
    │   ├── __init__.py
    │   ├── development
    │   │   ├── __init__.py
    │   │   └── settings.py
    │   ├── settings.py
    │   └── testing
    │       ├── __init__.py
    │       └── settings.py
    ├── main.py
    ├── serve.py
    ├── utils.py
    ├── tests
    │   ├── __init__.py
    │   └── test_app.py
    └── urls.py
```

Focus on `accounts/models.py`, where models for the `accounts` application are placed.

```python title="myproject/apps/accounts/models.py"
{!> ../docs_src/migrations/accounts_models.py !}
```

Use `preloads` to load the model file:

```python title="myproject/configs/settings.py"
{!> ../docs_src/migrations/attaching.py !}
```

Set `migrate_databases` if additional databases are used.

## Generating and Working with Migrations

Ensure you've read the [Migration](#migration) section and have everything set up.

Edgy's internal client, `edgy`, manages the migration process.

Refer to the project structure at the beginning of this document.

!!! Note
    The provided structure is for demonstration purposes; you can use any structure.

!!! danger
    Migrations can be generated anywhere, but be mindful of paths and dependencies. It's recommended to place them at the project root.

Assuming your application is in `my_project/main.py`, follow these steps.

### Environment Variables

Edgy uses the following environment variables for migrations:

* **EDGY_DATABASE**: Restricts migrations to the specified database metadata. Use a whitespace for the main database. Special mode when used with **EDGY_DATABASE_URL**.
* **EDGY_DATABASE_URL**: Two modes:
    1.  **EDGY_DATABASE** is empty: Retrieves metadata via URL. Default database used if no match, with differing URL.
    2.  **EDGY_DATABASE** is not empty: Uses metadata of the named database with a different URL.

Use the [`migrate_databases`](#migration-settings) setting instead of environment variables.

!!! Warning
    Spaces can be invisible. Verify **EDGY_DATABASE** for spaces or whitespace.

!!! Tip
    Change `MAIN_DATABASE_NAME` in `env.py` for a different main database name.

### Initialize the Migrations Folder

To begin, generate the migrations folder.

```shell
# code is in myproject.main
edgy init
# or specify an entrypoint module explicitly
# edgy --app myproject.main_test init
```

The [discovery mechanism](./discovery.md) automatically locates the entrypoint, but you can also provide it explicitly using `--app`.

The optional `--app` parameter specifies the application's location in `module_app` format, a necessity due to Edgy's framework-agnostic nature.

Edgy requires the module to automatically set the instance (see [Connections](../connection.md)), enabling it to determine the registry and application object.

The location where you execute the `init` command determines where the migrations folder is created.

For example, `my_project.main_test` indicates your application is in `myproject/main_test.py`, and the migration folder will be placed in the current directory.

After generating the migrations, the project structure will resemble this:

```shell hl_lines="4-9"
.
└── README.md
└── .gitignore
├── migrations
│   ├── alembic.ini
│   ├── env.py
│   ├── README
│   ├── script.py.mako
│   └── versions
└── myproject
    ├── __init__.py
    ├── apps
    │   ├── __init__.py
    │   └── accounts
    │       ├── __init__.py
    │       ├── tests.py
    │       └── v1
    │           ├── __init__.py
    │           ├── schemas.py
    │           ├── urls.py
    │           └── views.py
    ├── configs
    │   ├── __init__.py
    │   ├── development
    │   │   ├── __init__.py
    │   │   └── settings.py
    │   ├── settings.py
    │   └── testing
    │       ├── __init__.py
    │       └── settings.py
    ├── main.py
    ├── serve.py
    ├── utils.py
    ├── tests
    │   ├── __init__.py
    │   └── test_app.py
    └── urls.py
```

The migrations folder and its contents are automatically generated and tailored to Edgy's requirements.

#### Templates

Edgy offers various migration templates to customize the generation process.

* `default` (Default): Uses hashed database names and is compatible with Flask-Migrate multi-database migrations.
* `plain`: Uses plain database names (extra databases must be valid identifiers) and is compatible with Flask-Migrate. Extra database names are restricted to Python identifiers.
* `url`: Uses database URLs for hashing, suitable for non-local database environments. Requires adapting `env.py` due to incompatibility with Flask-Migrate. URL parameters used for hashing are `f"{url.username}@{url.hostname}:{url.port}/{url.database}"`.
* `sequential`: Uses a sequence of numbers for migration filenames (e.g., `0001_<SOMETHING>`).

Use these templates with:

```shell
edgy init -t plain
```

List all available templates:

```shell
edgy list_templates
```

You can also use templates from the filesystem:

```shell title="Example how to use the singledb template from tests"
edgy --app myproject.main init -t tests/cli/custom_singledb
```

Templates are starting points and may require customization.

### Generate the First Migrations

Generate your first migration.

Assume your `accounts` application models are in `models.py`. Define a `User` model:

```python title="my_project/apps/accounts/models.py"
{!> ../docs_src/migrations/model.py !}
```

Ensure the models are accessible for discovery. For Esmerald, add the `User` model to `my_project/apps/accounts/__init__.py`:

```python title="my_project/apps/accounts/__init__.py"
from .models import User
```

!!! Note
    Edgy, being framework-agnostic, doesn't use hard-coded detection like Django's `INSTALLED_APPS`. Use `preloads` and imports to load models.

Generate the migration:

```shell
$ edgy makemigrations
```

The new migration will be in `migrations/versions/`:

```shell hl_lines="10"
.
└── README.md
└── .gitignore
├── migrations
│   ├── alembic.ini
│   ├── env.py
│   ├── README
│   ├── script.py.mako
│   └── versions
│       └── d3725dd11eef_.py
└── myproject
    ...
```

Add a message to the migration:

```shell
$ edgy makemigrations -m "Initial migrations"
```

```shell hl_lines="10"
.
└── README.md
└── .gitignore
├── migrations
│   ├── alembic.ini
│   ├── env.py
│   ├── README
│   ├── script.py.mako
│   └── versions
│       └── d3725dd11eef_initial_migrations.py
└── myproject
    ...
```

### Migrate Your Database

Apply the migrations:

```shell
$ edgy migrate
```

### Change Models and Generate Migrations

Modify your models and generate new migrations:

**Generate new migrations:**

```shell
$ edgy makemigrations
```

**Apply them:**

```shell
$ edgy migrate
```

### More Migration Commands

Access available commands with `--help`:

## Edgy Command-Line

List available Edgy options:

```shell
$ edgy --help
```

View options for a specific command (e.g., `merge`):

```shell
$ edgy merge --help
```

```shell
Usage: edgy merge [OPTIONS] [REVISIONS]...

  Merge two revisions together, creating a new revision file

Options:
  --rev-id TEXT         Specify a hardcoded revision id instead of generating
                        one
  --branch-label TEXT   Specify a branch label to apply to the new revision
  -m, --message TEXT    Merge revision message
  -d, --directory TEXT  Migration script directory (default is "migrations")
  --help                Show this message and exit.
```

This applies to all Edgy commands.

### References

Edgy's command-line interface is user-friendly.

Edgy migrations use Alembic, so commands are similar, with two exceptions:

* `makemigrations`: Calls Alembic's `migrate`.
* `migrate`: Calls Alembic's `upgrade`.

Edgy uses more intuitive names.

## Migrate to new non-nullable fields

Sometimes you want to add fields to a model which are required afterwards.

### With server_default

This is a bit more work and requires a supported field (all single-column fields and some multiple-column fields like CompositeField). It works as follows:

1. Add a column with a server_default which is used by the migrations.
2. Create the migration and migrate.
3. Remove the server_default and create another migration.

Here is a basic example:

1.  Create the field with a server_default
    ``` python
    class CustomModel(edgy.Model):
        active: bool = edgy.fields.BooleanField(server_default=sqlalchemy.text("true"))
        ...
    ```
2.  Generate the migrations and migrate
    ``` sh
    edgy makemigration
    edgy migrate
    ```
3. Remove the server_default
    ``` python
    class CustomModel(edgy.Model):
        active: bool = edgy.fields.BooleanField()
        ...
    ```
4.  Generate the migrations without the server_default and migrate
    ``` sh
    edgy makemigration
    edgy migrate
    ```

### With null-field
Null-field is a feature to make fields nullable for one makemigration/revision. You can either specify
`model:field_name` or just `:field_name` for automatic detection of models.
Non-existing models are ignored, and only models in `registry.models` are migrated.
In the migration file, you will find a construct `monkay.instance.registry.apply_default_force_nullable_fields(...)`.
The `model_defaults` argument can be used to provide one-time defaults that overwrite all other defaults.
You can also pass callables, which are executed in context of the `extract_column_values` method and have all of the context variables available.

Let's see how to implement the last example with null-field and we add also ContentTypes.
1. Add the field with the default (not server-default).
    ``` python
    class CustomModel(edgy.Model):
        active: bool = edgy.fields.BooleanField(default=True)
        ...
    ```
2. Apply null-field to CustomModel:active and also for all models with active content_type.
    ``` sh
    edgy makemigration --nf CustomModel:active --nf :content_type
    edgy migrate
    ```
3. Now create a cleanup migration.
    ``` sh
    edgy makemigration
    edgy migrate
    ```

!!! Tip
    In case you mess up the null-fields, you can also fix them manually in the script file. You can also specify custom defaults for fields.

## Multi-Database Migrations

Edgy supports multi-database migrations. Continue using single-database migrations or update `env.py` and existing migrations.

### Migrate from Flask-Migrate

Flask-Migrate was the basis for the deprecated `Migrate` object. Use `edgy.Instance` and migration settings.

`edgy.Instance` takes `(registry, app=None)` as arguments, unlike Flask-Migrate's `(app, database)`. Settings are now in the Edgy settings object.

#### Migrate `env.py`

Replace `env.py` with Edgy's default. Adjust migrations if necessary.

### Migrate from Single-Database Migrations

Adapt old migrations for multi-database support:

1.  Add an `engine_name` parameter to `upgrade`/`downgrade` functions, defaulting to `''`.
2.  Prevent execution if `engine_name` is not empty.

For different default databases, add the database to extra and prevent execution for other names.

**Example:**

```python
def downgrade():
    ...
```

Becomes:

```python
def downgrade(engine_name: str = ""):
    if engine_name != "":  # or dbname you want
        return
```

## Multi-Schema Migrations

Enable multi-schema migrations by setting `multi_schema` in [Migration Settings](#migration-settings). Filter schemas using schema parameters.

## Migrations in libraries  and middleware

Edgy has not only an interface for main applications but also for libraries.
We can use edgy even in an asgi middleware when the main project is django.

To integrate there are two ways:

### Extensions

Add an extension which when included in edgy settings extensions is injecting the model in the

Pros:

- Reuses the registry and database.
- Migrations contain also the injected models.

Cons:

- Requires edgy as main application.
- Only one registry is supported.
- Not completely independent. Affected by settings.

### Automigrations



Pros:

- Can use an own registry and database. Completely independent from the main application.
- Ideal for asgi middleware.

Cons:

- Requires ddl access on the database it is using. In case of the offline mode of alembic,
  all libraries must be accessed manually via `edgy migrate -d librarypath/migrations`.
- Must maybe be disabled via `allow_automigrations=False` in edgy settings in case of missing permissions.

### What to use

The optimal way is to provide the user the extension way and a fallback way with automigrations which
reuses the extension way to inject in a registry.
