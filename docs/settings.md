# Settings

Who never had that feeling that sometimes haing some database settings would be nice? Well, since
Edgy is from the same author of Esmerald and since Esmerald is [settings][esmerald_settings] oriented, why not apply
the same principle but in a simpler manner but to Edgy?

This is exactly what happened.

## Edgy Setting Module

The way of using the settings object within a Edgy use of the ORM is via:

* **EDGY_SETTINGS_MODULE** environment variable.

All the settings are **[pydantic BaseSettings](https://pypi.org/project/pydantic-settings/)** objects which makes it easier to use and override
when needed.

### EDGY_SETTINGS_MODULE

Edgy by default uses is looking for a `EDGY_SETTINGS_MODULE` environment variable to run and
apply the given settings to your instance.

If no `EDGY_SETTINGS_MODULE` is found, Edgy then uses its own internal settings which are
widely applied across the system.

#### Custom settings

When creating your own custom settings class, you should inherit from `EdgySettings` which is
the class responsible for all internal settings of Edgy and those can be extended and overriden
with ease.

Something like this:

```python title="myproject/configs/settings.py"
{!> ../docs_src/settings/custom_settings.py !}
```

Super simple right? Yes and that is the intention. Edgy does not have a lot of settings but
has some which are used across the codebase and those can be overriden easily.

!!! Danger
    Be careful when overriding the settings as you might break functionality. It is your own risk
    doing it.

##### Parameters

* **ipython_args** - List of arguments passed to `ipython` when starting the `edgy shell`.

    <sup>Default: `["--no-banner"]`</sup>

* **ptpython_config_file** - Config file to be loaded into `ptpython` when starting the `edgy shell --kernel ptpython`.

    <sup>Default: `"~/.config/ptpython/config.py"`</sup>

* **postgres_dialects** - Set of available Postgres dialects supported by Edgy.

    <sup>Default: `{"postgres", "postgresql"}`</sup>

* **mysql_dialects** - Set of available MySQL dialects supported by Edgy.

    <sup>Default: `{"mysql"}`</sup>

* **sqlite_dialects** - Set of available SQLite dialects supported by Edgy.

    <sup>Default: `{"sqlite"}`</sup>

* **mssql_dialects** - Set of available MSSQL dialects supported by Edgy.

    <sup>Default: `{"mssql"}`</sup>

* **postgres_drivers** - Set of available Postgres drivers supported by Edgy.

    <sup>Default: `{"aiopg", "asyncpg"}`</sup>

* **mysql_drivers** - Set of available MySQL drivers supported by Edgy.

    <sup>Default: `{"aiomysql", "asyncmy"}`</sup>

* **sqlite_drivers** - Set of available SQLite drivers supported by Edgy.

    <sup>Default: `{aiosqlite}`</sup>

#### How to use it

Similar to [esmerald settings][esmerald_settings], Edgy uses it in a similar way.

Using the example [above](#custom-settings) and the location `myproject/configs/settings.py`, the
settings should be called like this:

```shell
$ EDGY_SETTINGS_MODULE=myproject.configs.settings.MyCustomSettings edgy <COMMAND>
```

Example:

**Starting the default shell**

```shell
$ EDGY_SETTINGS_MODULE=myproject.configs.settings.MyCustomSettings edgy shell
```

**Starting the PTPython shell**

```shell
$ EDGY_SETTINGS_MODULE=myproject.configs.settings.MyCustomSettings edgy shell --kernel ptpython
```

**Creating the migrations folder**

```shell
$ EDGY_SETTINGS_MODULE=myproject.configs.settings.MyCustomSettings edgy init
```

**Generating migrations**

```shell
$ EDGY_SETTINGS_MODULE=myproject.configs.settings.MyCustomSettings edgy makemigrations
```

**Appying migrations**

```shell
$ EDGY_SETTINGS_MODULE=myproject.configs.settings.MyCustomSettings edgy migrate
```

And the list goes on and on, you get the gist. Too understand which commands are available, check
the [commands](./migrations/migrations.md) available to you and the [shell support](./shell.md) for
the Edgy shell support.


[esmerald_settings]: https://esmerald.dev/application/settings/
