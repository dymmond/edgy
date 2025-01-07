# Application Discovery

Edgy has many different ways of understanding the commands, one is via
[environment variables](#environment-variables) and another is via [auto discovery](#auto-discovery).

## Auto Discovery

If you are familiar with other frameworks like Django, you are surely familiar with the way the
use the `manage.py` to basically run every command internally.

Although not having that same level, Edgy does a similar job by having "a guess" of what
it should be and throws an error if not found or if no [environment variables or --app](#environment-variables)
are provided.

**The application discovery works as an alternative to providing the `--app` or a `EDGY_DEFAULT_APP` environment variable**.

So, what does this mean?

This means if **you do not provide an --app or a EDGY_DEFAULT_APP**, Edgy will try to find the
application for you automatically.

Let us see a practical example of what does this mean.

Imagine the following folder and file structure:

```shell hl_lines="16" title="myproject"
.
├── Makefile
└── myproject
    ├── __init__.py
    ├── apps
    │   ├── __init__.py
    ├── configs
    │   ├── __init__.py
    │   ├── development
    │   │   ├── __init__.py
    │   │   └── settings.py
    │   ├── settings.py
    │   └── testing
    │       ├── __init__.py
    │       └── settings.py
    ├── main.py
    ├── tests
    │   ├── __init__.py
    │   └── test_app.py
    └── urls.py
```

!!! Tip
    The `application` can be anything from Esmerald, Starlette, Sanic and even FastAPI.

The structure above of `myproject` has a lot of files and the one higlighted is the one that
contains the application object with the [Migration](./migrations.md#migration) from Edgy.

### How does it work?

When no `--app` or no `EDGY_DEFAULT_APP` environment variable is provided, Edgy will
**automatically look for**:

* The current directory where `edgy` is being called contains a file called:
    * **main.py**
    * **app.py**
    * **application.py**
    * **asgi.py**

    (Or are otherwise importable by python without the .py stem)

    !!! Warning
        **If none of these files are found**, Edgy will look **at the first children nodes, only**,
        and repeats the same process. If no files are found then throws an `CommandEnvironmentError`
        exception.


* Once one of those files is found, Edgy will check if the instance was set.

This is the way that Edgy can `auto discover` your application.


## Environment variables

When generating migrations, Edgy can use two variables to detect the right database.

* **EDGY_DATABASE_URL** - The database url for your database.
* **EDGY_DATABASE** - The extra database name for your database.

By default the default database is used.

The reason for this is because Edgy is agnostic to any framework and this way it makes it easier
to work with the `migrations`.

Also, gives a clean design for the time where it is needed to go to production as the procedure is
very likely to be done using environment variables.

Or whatever connection string you are using.

## How to use and when to use it

Previously it was used a folder structure as example and then an explanation of how Edgy would
understand the auto discovery but in practice, how would that work?

**This is applied to any command within Edgy**.

Let us see again the structure, in case you have forgotten already.

```shell hl_lines="20" title="myproject"
.
├── Makefile
└── src
    ├── __init__.py
    ├── apps
    │   ├── accounts
    │   │   ├── directives
    │   │   │   ├── __init__.py
    │   │   │   └── operations
    │   │   │       └── __init__.py
    ├── configs
    │   ├── __init__.py
    │   ├── development
    │   │   ├── __init__.py
    │   │   └── settings.py
    │   ├── settings.py
    │   └── testing
    │       ├── __init__.py
    │       └── settings.py
    ├── main.py
    ├── tests
    │   ├── __init__.py
    │   └── test_app.py
    └── urls.py
```

The `main.py` is the file that contains the edgy migration. A file that could look like
this:

```python title="myproject/src/main.py"
{!> ../docs_src/commands/discover.py !}
```

This is a simple example with two endpoints, you can do as you desire with the patterns you wish to
add and with any desired structure.

What will be doing now is run the following commands using the [auto discovery](#auto-discovery)
and the [--app or EDGY_DEFAULT_APP](#environment-variables):

* **init** - Starts the migrations and creates the migrations folder.
* **makemigrations** - Generates the migrations for the application.

We will be also executing the commands inside `myproject`.

**You can see more information about these [commands](./migrations.md), including**
**parameters, in the next section.**

### Using the auto discover

#### init

##### Using the auto discover

```shell
$ edgy init
```

Yes! Simply this and because not the `--app` or a `EDGY_DEFAULT_APP` was provided nor preloads were found, it triggered the
auto discovery of the application that contains the edgy information.

Because the application is inside `src/main.py` it will be automatically discovered by Edgy as
it followed the [discovery pattern](#how-does-it-work).

##### Using preloads

Edgy has an automatic registration pattern. All what `--app` or `EDGY_DEFAULT_APP` does is to import a file.
The registration is expected to take place in the module automatically.
Thanks to Monkay you can also provide such an import path as preload under
`preloads` in settings.
When the instance is set in a preloaded file, the auto-discovery is skipped.


##### Using the --app or EDGY_DEFAULT_APP

This is the other way to tell Edgy where to find your application. Since the application is
inside the `src/main.py` we need to provide the proper location is a `<module>` format.

###### --app

With the `--app` flag.

```shell
$ edgy --app src.main init
```

###### EDGY_DEFAULT_APP

With the `EDGY_DEFAULT_APP`.

Export the env var first:

```shell
$ export EDGY_DEFAULT_APP=src.main
```

And then run:

```shell
$ edgy init
```

#### makemigrations

You can see [more details](./migrations.md#migrate-your-database) how to use it.

It is time to run this command.

##### Using the auto discover

```shell
$ edgy makemigrations
```

Again, same principle as before because the `--app` or a `EDGY_DEFAULT_APP` was provided,
it triggered the auto discovery of the application.

##### Using the --app or EDGY_DISCOVERY_APP

!!! Note
    There was a change in 0.23.0: the import path must be to a module in which the registration via the `Instance` object is automatically triggered.
    See [Connection](../connection.md).

###### --app

With the `--app` parameter.

```shell
$ edgy --app src.main makemigrations
```

###### EDGY_DEFAULT_APP

With the `EDGY_DEFAULT_APP`.

Export the env var first:

```shell
$ export EDGY_DEFAULT_APP=src.main
```

And then run:

```shell
$ edgy makemigrations
```
