# Settings

Who never had that feeling that sometimes haing some database settings would be nice? Well, since
Edgy is from the same author of Esmerald and since Esmerald is [settings][esmerald_settings] oriented, why not apply
the same principle but in a simpler manner but to Edgy?

This is exactly what happened.

## Edgy Settings Module

The way of using the settings object within a Edgy use of the ORM is via:

* **EDGY_SETTINGS_MODULE** environment variable.

All the settings are **[Pydantic BaseSettings](https://pypi.org/project/pydantic-settings/)** objects which makes it easier to use and override
when needed.

### EDGY_SETTINGS_MODULE

Edgy by default uses is looking for a `EDGY_SETTINGS_MODULE` environment variable to run and
apply the given settings to your instance.

If no `EDGY_SETTINGS_MODULE` is found, Edgy then uses its own internal settings which are
widely applied across the system.

#### Custom settings

When creating your own custom settings class, you should inherit from `EdgySettings` (or the subclass `TenancySettings` in case of multi tenancy). `EdgySettings` is
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

* **preloads** - List of imports preloaded. Non-existing imports are simply ignored.
  Can be used to inject a path to a module in which the instance is set.
  It takes strings in format `module` and `module:fn`. In the later case the function or callable is executed without arguments.

    <sup>Default: `[]`</sup>

* **extensions** - List of Monkay extensions for edgy. See [Extensions](./extensions.md) for more details. Extensions can of course also preload imports.

    <sup>Default: `[]`</sup>

* **ipython_args** - List of arguments passed to `ipython` when starting the `edgy shell`.

    <sup>Default: `["--no-banner"]`</sup>

* **ptpython_config_file** - Config file to be loaded into `ptpython` when starting the `edgy shell --kernel ptpython`.

    <sup>Default: `"~/.config/ptpython/config.py"`</sup>


#### How to use it

Similar to [esmerald settings][esmerald_settings], Edgy uses it in a similar way.

Using the example [above](#custom-settings) and the location `myproject/configs/settings.py`, the
settings should be called like this:

```shell
$ EDGY_SETTINGS_MODULE=myproject.configs.settings.MyCustomSettings edgy <COMMAND>
```

Optional prequesite: set one of the preload imports to the application path. This way you can skip
providing the `--app` parameter or providing the `EDGY_DEFAULT_APP`.

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

And the list goes on and on, you get the gist. To understand which commands are available, check
the [commands](./migrations/migrations.md) available to you and the [shell support](./shell.md) for
the Edgy shell support.


[esmerald_settings]: https://esmerald.dev/application/settings/
