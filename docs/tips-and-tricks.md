# Tips and Tricks for Edgy

This section provides guidance on organizing your code, particularly within an [Esmerald](https://esmerald.dymmond.com) application. While the examples are Esmerald-centric, the principles apply to any framework you use with Edgy.

## Centralizing Database Connections

Declaring database connections repeatedly throughout your application can lead to redundancy and potential issues with object identity. By centralizing your connections, you ensure consistency and prevent the creation of unnecessary objects.

### Global Settings File

A common approach is to store connection details in a global settings file. This is especially convenient with Esmerald, which provides easy access to settings throughout your application.

Example:

```python hl_lines="20-28"
{!> ../docs_src/tips/settings.py !}
```

With this setup, you can access the `db_connection` from anywhere in your code. In Esmerald:

```python hl_lines="3"
from esmerald.conf import settings

registry = settings.db_connection
```

However, merely placing the connection details in a settings file isn't sufficient to ensure object identity. Each time you access `settings.db_connection`, a new object is created. To address this, we use the `lru_cache` technique.

## The LRU Cache

LRU stands for "Least Recently Used." It's a caching technique that ensures functions with the same arguments return the same cached object. This prevents redundant object creation, which is crucial for maintaining consistent database connections.

Create a `utils.py` file to apply the `lru_cache` to your `db_connection`:

```python title="utils.py"
{!> ../docs_src/tips/lru.py !}
```

Now, you can import `get_db_connection()` anywhere in your application and always get the same connection and registry instance.

**Important:** You cannot place `get_db_connection()` in the same file as your application entry point. In such cases, use the [`edgy.monkay.instance`](#excurse-the-edgymonkayinstance-sandwich) sandwich technique.

## Excurse: The `edgy.monkay.instance` Sandwich

If you prefer to consolidate your code within `main.py`, you can use manual post-loads and initialize connections within `get_application`. This involves:

1.  Creating the registry.
2.  Assigning the instance to `edgy.instance` using `set_instance()` (without app and skipping extensions).
3.  Post-loading models.
4.  Creating the main app.
5.  Assigning the instance to `edgy.instance` using `set_instance()` (with app).

Example `main.py`:

````python title="main.py"
{!> ../docs_src/tips/sandwich_main.py !}
````

Example `myproject/models.py`:

````python title="myproject/models.py"
{!> ../docs_src/tips/sandwich_models.py !}
````

The sandwich method is limited to a single registry, while `lru_cache` allows for multiple parallel registries.

## Practical Example

Let's assemble a practical application with:

* A `User` model.
* [Migrations](./migrations/migrations.md) ready.
* Database connection setup.

Project structure:

```shell
.
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

### Settings

Define database connection properties in `settings.py`:

```python title="my_project/configs/settings.py" hl_lines="20-28 30-35"
{!> ../docs_src/tips/settings.py !}
```

### Utils

Create `utils.py` with the `lru_cache` implementation:

```python title="myproject/utils.py"
{!> ../docs_src/tips/lru.py !}
```

**Note:** Importing settings directly is not possible here. Wait until `build_path` is called.

### Models

Create models in `myproject/apps/accounts/models.py`:

```python title="myproject/apps/accounts/models.py" hl_lines="8 19"
{!> ../docs_src/tips/models.py !}
```

Use [inheritance](./models.md#with-inheritance) for cleaner code. Import `get_db_connection()` to ensure consistent registry usage.

### Prepare for Migrations

Configure the application for Edgy migrations in `main.py`:

```python title="myproject/main.py" hl_lines="10 32 38-42 44"
{!> ../docs_src/tips/migrations.py !}
```

### Hook the Connection

Hook the database connection in `main.py` using a settings forwarder for centralized configuration management:

```python title="myproject/main.py" hl_lines="32-38 40 48-52 54"
{!> ../docs_src/tips/connection.py !}
```

## Notes

This example demonstrates how to centralize connection management using `lru_cache` and settings files. Apply these techniques to your favorite frameworks and adapt them to your specific needs. Edgy is framework-agnostic, providing flexibility and consistency in your database interactions.
