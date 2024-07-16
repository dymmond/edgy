# Migrations

You will almost certainly need to be using a database migration tool to make sure you manage
your incremental database changes properly.

Edgy being on the top of SQLAlchemy core means that we can leverage that within the internal
migration tool.

Edgy provides an internal migration tool that makes your life way easier when it comes to manage
models and corresponding migrations.

Heavily inspired by the way Flask-Migration approached the problem, Edgy took it to the next
level and makes it framework agnostic, which means you can use it **anywhere**.

## Important

Before reading this section, you should get familiar with the ways Edgy handles the discovery
of the applications.

The following examples and explanations will be using the
[--app and environment variables](./discovery.md#environment-variables) approach but the
[auto discovery](./discovery.md#auto-discovery) is equally valid and works in the same way.

## Structure being used for this document

For the sake of this document examples and explanations we will be using the following structure to
make visually clear.

```shell
.
└── README.md
└── .gitignore
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

## Migration

This is the object that Edgy requires to make sure you can manage the migrations in a consistent,
clean and simple manner. Much like Django migrations type of feeling.

This `Migration` class is not depending of any framework specifically, in fact, Edgy makes sure
when this object is created, it will plug it into any framework you desire.

This makes Edgy unique and extremely flexible to be used within any of the Frameworks out there,
such as [Esmerald](https://esmerald.dymmond.com), Starlette, FastAPI, Sanic... You choose.

```python
from edgy import Migrate
```

### Parameters

The parameters availabe when using instantiating a [Migrate](#migration) object are the following:

* **app** - The application instance. Any application you want your migrations to be attached to.
* **registry** - The registry being used for your models. The registry **must be** an instance
of `edgy.Registry` or an `AssertationError` is raised.
* **model_apps** - A dictionary like object containing the string name and the location of the models
used for inspection.
* **compare_type** - Flag option that configures the automatic migration generation subsystem
to detect column type changes.

    <sup>Default: `True`</sup>

* **render_as_batch** - This option generates migration scripts using batch mode, an operational
mode that works around limitations of many ALTER commands in the SQLite database by implementing
a "move and copy" workflow. Enabling this mode should make no difference when working with other
databases.

    <sup>Default: `True`</sup>

* **kwargs** - A python dictionary with any context variables to be added to alembic.

    <sup>Default: `None`</sup>

### How to use it

Using the [Migration](#migration) class is very simple in terms of requirements. In the
[tips and tricks](../tips-and-tricks.md) you can see some examples in terms of using the
[LRU cache technique](../tips-and-tricks.md#the-lru-cache). If you haven't seen it,
it is recommended you to have a look.

For this examples, we will be using the same approach.

Assuming you have a `utils.py` where you place your information about the database and
[registry](../registry.md).

Something like this:

```python title="my_project/utils.py" hl_lines="6-9"
{!> ../docs_src/migrations/lru.py !}
```

This will make sure we don't create objects. Nice technique and quite practical.

Now that we have our details about the database and registry, it is time to use the
[Migration](#migration) object in the application.

#### Using Esmerald

```python title="my_project/main.py" hl_lines="9 12 32 38"
{!> ../docs_src/migrations/migrations.py !}
```

#### Using FastAPI

As mentioned before, Edgy is framework agnostic so you can also use it in your FastAPI
application.

```python title="my_project/main.py" hl_lines="6 9 29 33"
{!> ../docs_src/migrations/fastapi.py !}
```

#### Using Starlette

The same goes for Starlette.

```python title="my_project/main.py" hl_lines="6 9 29 33"
{!> ../docs_src/migrations/starlette.py !}
```

#### Using other frameworks

I believe you got the idea with the examples above, It was not specified any special framework
unique-like parameter that demanded special attention, just the application itself.

This means you can plug something else like Quart, Ella or even Sanic... Your pick.

### Using the `model_apps`

Since Edgy is framework agnostic, there is no way sometimes to tell where the models are unless
you are using them somewhere and this can be annoying if you want to generate migrations and manage
them without passing the models into the `__init__.py` of a python module

The **Migrate** object allows also to pass an extra parameter called `model_apps`. This is nothing
more nothing less than the location of the file containing the models used by your same application.

There are **three ways of passing values into the model_apps**.

* Via [dictionary](#via-dictionary).
* Via [tuple](#via-tuple).
* Via [list](#via-list).

#### Example

Let us assume we have an application with the following structure.

```shell
.
└── README.md
└── .gitignore
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

As you can see, it is quite structured but let us focus specifically on `accounts/models.py`.

There is where your models for the `accounts` application will be placed. Something like this:

```python
{!> ../docs_src/migrations/accounts_models.py !}
```

Now we want to tell the **Migrate** object to make sure it knows about this.

##### Via dictionary

```python
{!> ../docs_src/migrations/via_dict.py !}
```

As you can see the `model_apps = {"accounts": "accounts.models"}` was added in a simple fashion.
Every time you add new model or any changes, it should behave as normal as before with the key difference
that **now Edgy has a way to know exactly where your models are specifically**.

##### Via tuple

```python
{!> ../docs_src/migrations/via_tuple.py !}
```

The same for the tuple. You can simply pass `("accounts.models",)` as the location for the models.

##### Via list

```python
{!> ../docs_src/migrations/via_list.py !}
```
Finally, for the `list`. You can pass `["accounts.models"]` as the location for the models.

## Generating and working with migrations

Now this is the juicy part, right? Yes but before jumping right into this, please make sure you
read properly the [migration](#migration) section and you have everything in place.

**It is recommended that you follow** the [environment variables](#environment-variables)
suggestions.

This will depend heavily on this and **everything works around the registry**.

Edgy has the internal client that manages and handles the migration process for you in a clean
fashion and it called `edgy`.

Remember the initial structure at the top of this document? No worries, let us have a look again.

```shell
.
└── README.md
└── .gitignore
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

This structure is important as it will make it easier to explain where you should start with
migrations.

!!! Note
    Using the above structure helps for visual purposes but by the end of this document, you don't
    need to follow this way, you can do whatever you want.

!!! danger

    You can generate the migrations **anywhere** in your codebase but you need to be careful about the
    paths and all of the internal dependencies. It is recommended to have them at the root of your
    project, but again, up to you.

Assuming you have your application inside that `my_project/main.py` the next steps will follow
that same principle.

### Environment variables

When generating migrations, Edgy **expects at least one environment variable to be present**.

* **EDGY_DATABASE_URL** - The database url for your database.

The reason for this is because Edgy is agnostic to any framework and this way it makes it easier
to work with the `migrations`.

Also, gives a clean design for the time where it is needed to go to production as the procedure is
very likely to be done using environment variables.

**This variable must be present**. So to save time you can simply do:

```
$ export EDGY_DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/my_database
```

Or whatever connection string you are using.

### Initialise the migrations folder

It is now time to generate the migrations folder. As mentioned before in the
[environment variables section](#environment-variables), Edgy does need to have the
`EDGY_DATABASE_URL` to generate the `migrations` folder. So, without further ado let us generate
our `migrations`.

```shell
edgy --app myproject.main:app init
```

What is happenening here? Well, `edgy` is always expecting an `--app` parameter to be
provided.

This `--app` is the location of your application in `module:app` format and this is because of
the fact of being **framework agnostic**.

Edgy needs to know where your application object is located in order to hook it to that same
application.

Remember when it was mentioned that is important the location where you generate the migrations
folder? Well, this is why, because when you do `my_project.main:app` you are telling that
your application is inside the `myproject/main/app.py` and your migration folder should be placed
**where the command was executed**.

In other words, the place you execute the `init` command it will be where the migrations will be
placed.

Let us see how our structrure now looks like after generating the migrations.

```shell hl_lines="4-9"
.
└── README.md
└── .gitignore
├── migrations
│   ├── alembic.ini
│   ├── env.py
│   ├── README
│   ├── script.py.mako
│   └── versions
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

Pretty great so far! Well done 🎉🎉

You have now generated your migrations folder and came with gifts.

A lot of files were generated automatically for you and they are specially tailored for the needs
and complexity of **Edgy**.

Do you remember when it was mentioned in the [environment variables](#environment-variables) that
edgy is expecting the `EDGY_DATABASE_URL` to be available?

Well, this is another reason, inside the generated `migrations/env.py` the `get_engine_url()` is
also expecting that value.

```python title="migrations/env.py"
# Code above

def get_engine_url():
    return os.environ.get("EDGY_DATABASE_URL")

# Code below
```

!!! Warning
    You do not need to use this environment variable. This is the `default` provided by Edgy.
    You can change the value to whatever you want/need but be careful when doing it as it might
    cause Edgy not to work properly with migrations if this value is not updated properly.

### Generate the first migrations

Now it is time to generate your first migration.

Assumming we want to place the models for an `accounts` application inside a `models.py`.

Let us define our `User` model.

```python title="my_project/apps/accounts/models.py"
{!> ../docs_src/migrations/model.py !}
```

Now we need to make sure the models are accessible in the application for discovery. Since
this example is based on Esmerald scaffold, simply add your `User` model into the
`my_project/apps/accounts/__init__.py`.

```python title="my_project/apps/accounts/__init__.py"
from .models import User
```

!!! Note
    Since Edgy is agnostic to any framework, there aren't automatic mechanisms that detects
    Edgy models in the same fashion that Django does with the `INSTALLED_APPS`. So this is
    one way of exposing your models in the application.

There are many ways of exposing your models of course, so feel free to use any approach you want.

Now it is time to generate the migration.

```shell
$ edgy --app my_project.main:app makemigrations
```

Yes, it is this simple 😁

Your new migration should now be inside `migrations/versions/`. Something like this:

```shell hl_lines="10"
.
└── README.md
└── .gitignore
├── migrations
│   ├── alembic.ini
│   ├── env.py
│   ├── README
│   ├── script.py.mako
│   └── versions
│       └── d3725dd11eef_.py
└── myproject
    ...
```

Or you can attach a message your migration that will then added to the file name as well.

```shell
$ edgy --app my_project.main:app makemigrations -m "Initial migrations"
```

```shell hl_lines="10"
.
└── README.md
└── .gitignore
├── migrations
│   ├── alembic.ini
│   ├── env.py
│   ├── README
│   ├── script.py.mako
│   └── versions
│       └── d3725dd11eef_initial_migrations.py
└── myproject
    ...
```

### Migrate your database

Now comes the easiest part where you need to apply the migrations.

Simply run:

```shell
$ edgy --app my_project.main:app migrate
```

And that is about it 🎉🎉

You have managed to create the migrations, generate the files and migrate them in some simple steps.

### Change the models and generate the migrations

Well, it is not rocket science here. You can change your models as you please like you would do
for any other ORM and when you are happy run the migrations and apply them again by running:

**Generate new migrations**

```shell
$ edgy --app my_project.main:app makemigrations
```

**Apply them to your database**

```shell
$ edgy --app my_project.main:app migrate
```

### More migration commands

There are of course more available commands to you to be used which they can also be accessed
via `--help` command.

## Edgy admin

To access the available options of edgy:

```shell
$ edgy --help
```

This will list all the commands available within `edgy`.

**What if you need to also know the available options available to each command?**

Let us imagine you want to see the available options for the `merge`

```shell
$ edgy merge --help
```

You should see something like this:

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

This is applied to any other available command via `edgy`.

### References

Since Edgy has a very friendly and familiar interface to interact with so does the
`edgy`.

Edgy migrations as mentioned before uses Alembic and therefore the commands are exactly the
same as the ones for alembic except two, which are masked with different more intuitive names.

* **makemigrations** - Is calling the Alembic `migrate`.
* **migrate** - Is calling the Alembic `upgrade`.

Since the alembic names for those two specific operations is not that intuitive, Edgy masks them
into a more friendly and intuitive way.

For those familiar with Django, the names came from those same operations.

## Very important

Check the [environment variables](#environment-variables) for more details and making sure you follow the right steps.
