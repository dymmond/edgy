# Automatic Reflection

Automatic reflection in Edgy allows you to dynamically generate models from existing database tables. This is particularly useful for creating procedural interfaces or integrating with legacy databases.

Edgy provides `AutoReflectModel` to automate this process, using pattern matching to select tables and customizable templates to generate model names.

```python
from edgy.contrib.autoreflection import AutoReflectModel

class Reflected(AutoReflectModel):
    class Meta:
        include_pattern = ".*"  # Regex or string, matches table names (default: ".*")
        exclude_pattern = None  # Regex or string, excludes table names (default: None)
        template = "{modelname}{tablename}"  # String or function for model name generation
        databases = (None,)  # Databases to reflect (None: main database, string: extra database)
        schemes = (None,) # Schemes to check for tables.
```

When a reflected model is generated, its `Meta` class is converted to a regular `MetaInfo`.

## Meta Parameters Explained

Understanding the `Meta` parameters is crucial for effective automatic reflection.

**Key Concepts:**

* **Table Name:** The actual name of the table in the database.
* **Table Key:** The fully qualified name of the table, including the schema (e.g., `schema.tablename`).

Edgy handles schemas differently, allowing a model to exist in multiple schemas, with explicit schema selection during queries.

### Inclusion & Exclusion Patterns

These parameters use regular expressions to filter tables for reflection.

* **`include_pattern`:** Matches table names to include. Defaults to `.*` (all tables). Falsy values are converted to the match-all pattern.
* **`exclude_pattern`:** Matches table names to exclude. Defaults to `None` (disabled).

### Template

The `template` parameter controls how model names are generated. It can be:

* **A function:** Takes the table name as an argument and returns a string.
* **A format string:** Uses placeholders like `{tablename}`, `{tablekey}`, and `{modelname}`.

### Databases

The `databases` parameter specifies which databases to reflect.

* **`None`:** The main database defined in the registry.
* **String:** The name of an extra database defined in the registry's `extra` dictionary.

By default, only the main database is reflected.

### Schemes

The `schemes` parameter specifies which database schemas to scan for tables.

This is required when the tables to be reflected are located in a schema other than the default.

## Examples: Practical Applications of Automatic Reflection

Let's explore some practical examples of how automatic reflection can be used.

### Procedural Interface Generation

Imagine you need to create an application with a data-driven approach, where models are generated automatically from existing tables.

First, create the tables using:

```python title="source.py"
{!> ../docs_src/reflection/autoreflection/datadriven_source.py !}
```

Then, reflect the tables into models:

```python title="procedural.py"
{!> ../docs_src/reflection/autoreflection/datadriven.py !}
```

### Integrating with Legacy Databases

Suppose you have a modern database, a legacy database, and an ancient database. You need to access data from all three, but you're only allowed to update specific fields in the legacy and ancient databases.

```python title="legacy.py"
{!> ../docs_src/reflection/autoreflection/legacy.py !}
```

In this example, `LegacyModel` and `AncientModel` are automatically generated from the legacy and ancient databases, allowing you to access their data while adhering to their update restrictions.
