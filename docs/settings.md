# Settings in Edgy

Have you ever wished you could easily configure database settings? Since Edgy is created by the same author as Ravyn, and Ravyn is [settings][ravyn_settings] oriented, Edgy adopts a similar approach, albeit in a simpler form.

## Edgy Settings Module

Edgy uses the following environment variable to locate its settings:

* **EDGY_SETTINGS_MODULE**

All settings are **[Pydantic BaseSettings](https://pypi.org/project/pydantic-settings/)** objects, making them easy to use and override.

### EDGY_SETTINGS_MODULE

Edgy looks for the `EDGY_SETTINGS_MODULE` environment variable to load and apply settings.

If `EDGY_SETTINGS_MODULE` is not found, Edgy uses its internal default settings.

#### Custom Settings

To create custom settings, inherit from `EdgySettings` (or `TenancySettings` for multi-tenancy). `EdgySettings` handles Edgy's internal settings, which you can extend or override.

Example:

```python title="myproject/configs/settings.py"
{!> ../docs_src/settings/custom_settings.py !}
```

Edgy's settings are designed to be simple and easily overridable.

!!! Danger
    Exercise caution when overriding settings, as it may break functionality.

##### Parameters

* **preloads**: List of imports to preload. Non-existent imports are ignored. Can be used to inject a path to a module in which the instance is set. Takes strings in format `module` and `module:fn`. In the latter case the function or callable is executed without arguments.

    <sup>Default: `[]`</sup>

* **extensions**: List of Monkay extensions for Edgy. See [Extensions](./extensions.md) for details. Extensions can also preload imports.

    <sup>Default: `[]`</sup>

* **ipython_args**: List of arguments passed to `ipython` when starting `edgy shell`.

    <sup>Default: `["--no-banner"]`</sup>

* **ptpython_config_file**: Config file loaded into `ptpython` when starting `edgy shell --kernel ptpython`.

    <sup>Default: `"~/.config/ptpython/config.py"`</sup>

#### How to Use It

Similar to [Ravyn settings][ravyn_settings], Edgy uses the `EDGY_SETTINGS_MODULE` environment variable.

Using the example from [above](#custom-settings) and the location `myproject/configs/settings.py`, the settings should be called like this:

```shell
$ EDGY_SETTINGS_MODULE=myproject.configs.settings.MyCustomSettings edgy <COMMAND>
```

Optional prerequisite: set one of the preload imports to the application path. This way you can skip providing the `--app` parameter or providing the `EDGY_DEFAULT_APP`.

Example:

**Starting the default shell:**

```shell
$ EDGY_SETTINGS_MODULE=myproject.configs.settings.MyCustomSettings edgy shell
```

**Starting the PTPython shell:**

```shell
$ EDGY_SETTINGS_MODULE=myproject.configs.settings.MyCustomSettings edgy shell --kernel ptpython
```

**Creating the migrations folder:**

```shell
$ EDGY_SETTINGS_MODULE=myproject.configs.settings.MyCustomSettings edgy init
```

**Generating migrations:**

```shell
$ EDGY_SETTINGS_MODULE=myproject.configs.settings.MyCustomSettings edgy makemigrations
```

**Applying migrations:**

```shell
$ EDGY_SETTINGS_MODULE=myproject.configs.settings.MyCustomSettings edgy migrate
```

And so on. To see available commands, check the [commands](./migrations/migrations.md) and [shell support](./shell.md).

[ravyn_settings]: https://ravyn.dev/application/settings/
