# Settings

Who never had that feeling that sometimes haing some database settings would be nice? Well, since
Saffier is from the same author of Esmerald and since Esmerald is [settings][esmerald_settings] oriented, why not apply
the same principle but in a simpler manner but to Saffier?

This is exactly what happened.

## Saffier Setting Module

The way of using the settings object within a Saffier use of the ORM is via:

* **SAFFIER_SETTINGS_MODULE** environment variable.

All the settings are **[pydantic BaseSettings](https://pypi.org/project/pydantic-settings/)** objects which makes it easier to use and override
when needed.

### SAFFIER_SETTINGS_MODULE

Saffier by default uses is looking for a `SAFFIER_SETTINGS_MODULE` environment variable to run and
apply the given settings to your instance.

If no `SAFFIER_SETTINGS_MODULE` is found, Saffier then uses its own internal settings which are
widely applied across the system.

#### Custom settings

When creating your own custom settings class, you should inherit from `SaffierSettings` which is
the class responsible for all internal settings of Saffier and those can be extended and overriden
with ease.

Something like this:

```python title="myproject/configs/settings.py"
{!> ../docs_src/settings/custom_settings.py !}
```

Super simple right? Yes and that is the intention. Saffier does not have a lot of settings but
has some which are used across the codebase and those can be overriden easily.

!!! Danger
    Be careful when overriding the settings as you might break functionality. It is your own risk
    doing it.

##### Parameters

* **ipython_args** - List of arguments passed to `ipython` when starting the `saffier shell`.

    <sup>Default: `["--no-banner"]`</sup>

* **ptpython_config_file** - Config file to be loaded into `ptpython` when starting the `saffier shell --kernel ptpython`.

    <sup>Default: `"~/.config/ptpython/config.py"`</sup>

* **postgres_dialects** - Set of available Postgres dialects supported by Saffier.

    <sup>Default: `{"postgres", "postgresql"}`</sup>

* **mysql_dialects** - Set of available MySQL dialects supported by Saffier.

    <sup>Default: `{"mysql"}`</sup>

* **sqlite_dialects** - Set of available SQLite dialects supported by Saffier.

    <sup>Default: `{"sqlite"}`</sup>

* **mssql_dialects** - Set of available MSSQL dialects supported by Saffier.

    <sup>Default: `{"mssql"}`</sup>

* **postgres_drivers** - Set of available Postgres drivers supported by Saffier.

    <sup>Default: `{"aiopg", "asyncpg"}`</sup>

* **mysql_drivers** - Set of available MySQL drivers supported by Saffier.

    <sup>Default: `{"aiomysql", "asyncmy"}`</sup>

* **sqlite_drivers** - Set of available SQLite drivers supported by Saffier.

    <sup>Default: `{aiosqlite}`</sup>

#### How to use it

Similar to [esmerald settings][esmerald_settings], Saffier uses it in a similar way.

Using the example [above](#custom-settings) and the location `myproject/configs/settings.py`, the
settings should be called like this:

```shell
$ SAFFIER_SETTINGS_MODULE=myproject.configs.settings.MyCustomSettings saffier <COMMAND>
```

Example:

**Starting the default shell**

```shell
$ SAFFIER_SETTINGS_MODULE=myproject.configs.settings.MyCustomSettings saffier shell
```

**Starting the PTPython shell**

```shell
$ SAFFIER_SETTINGS_MODULE=myproject.configs.settings.MyCustomSettings saffier shell --kernel ptpython
```

**Creating the migrations folder**

```shell
$ SAFFIER_SETTINGS_MODULE=myproject.configs.settings.MyCustomSettings saffier init
```

**Generating migrations**

```shell
$ SAFFIER_SETTINGS_MODULE=myproject.configs.settings.MyCustomSettings saffier makemigrations
```

**Appying migrations**

```shell
$ SAFFIER_SETTINGS_MODULE=myproject.configs.settings.MyCustomSettings saffier migrate
```

And the list goes on and on, you get the gist. Too understand which commands are available, check
the [commands](./migrations/migrations.md) available to you and the [shell support](./shell.md) for
the Saffier shell support.


[esmerald_settings]: https://esmerald.dev/application/settings/
