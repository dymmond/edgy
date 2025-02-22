Absolutely! Let's expand on this section with thorough explanations for the end user.

# Shell Support

Have you ever found yourself needing to quickly interact with your database models directly from the command line? Perhaps you wanted to test a query, inspect data, or perform some quick data manipulation without writing a full script. If you've struggled with setting up such an environment in the past, Edgy's shell support is designed to make your life easier.

Edgy provides an interactive Python shell that automatically loads your application's models, allowing you to seamlessly interact with your database. This feature is incredibly useful for development, debugging, and exploration.

!!! Warning
    While the Edgy shell is a powerful tool, it's generally not recommended for use in production environments. Its primary purpose is for development and debugging.

## Important: Application Discovery

Before diving into the shell, it's crucial to understand how Edgy discovers your application. The shell relies on the same discovery mechanisms used by Edgy's migration system.

The following examples will primarily demonstrate the [auto-discovery](./migrations/discovery.md#auto-discovery) approach, but the concepts are equally applicable to the [--app and environment variables](./migrations/discovery.md#environment-variables) method.

## How It Works: Behind the Scenes

Edgy's shell functionality is designed to be user-friendly, abstracting away much of the underlying complexity. Here's a simplified breakdown of what happens when you launch the Edgy shell:

1.  **Application Discovery:** Edgy uses the same logic as its migration system to locate your application. This involves identifying the application where your Edgy models are defined.
2.  **Registry Extraction:** Once the application is located, Edgy extracts the [registry](./registry.md) object. The registry is responsible for managing your database connection and model definitions.
3.  **Model Loading:** Edgy then automatically loads all your defined [models](./models.md) and [reflected models](./reflection/reflection.md) into the interactive Python shell's namespace. This makes them readily available for you to use.
4.  **Shell Initialization:** Finally, Edgy initializes the interactive Python shell, providing you with a ready-to-use environment for interacting with your models.

This process ensures that your shell environment is correctly configured and that all your models are accessible, saving you the time and effort of manually setting up these components.

### Requirements: Installing Interactive Shells

Edgy's shell support integrates with popular interactive Python shells, specifically `ipython` and `ptpython`. To use the Edgy shell, you'll need to have one or both of these installed.

**IPython:**

IPython is a powerful interactive shell that provides enhanced features like tab completion, syntax highlighting, and magic commands.

To install IPython:

```shell
$ pip install ipython
```

**PTPython:**

PTPython is another excellent interactive Python shell that offers features like auto-completion, syntax highlighting, and multiline editing.

To install PTPython:

```shell
$ pip install ptpython
```

Having these shells installed enables you to choose your preferred interactive environment when using the Edgy shell.

### How to call it

#### With [auto discovery](./migrations/discovery.md#auto-discovery)

**Default shell**

```shell
$ edgy shell
```

**PTPython shell**

```shell
$ edgy shell --kernel ptpython
```

#### With [--app and environment variables](./migrations/discovery.md#environment-variables)

**--app**

```shell
$ edgy --app myproject.main shell
```

**Environment variables**

```shell
$ export EDGY_DEFAULT_APP=myproject.main
$ edgy shell --kernel ptpython
```

### How does it look like

Edgy doesn't want to load all python globals and locals for you. Instead loads all the
essentials for the models and reflected models and some python packages.

It looks like this:

<img src="https://res.cloudinary.com/tarsild/image/upload/v1691426975/packages/edgy/resources/edgy_shell_dqx9bf.png" alt='Shell Example'>

Of course the `EDGY-VERSION` and `APPLICATION` are replaced automatically by the version you are
using.

#### Example

Let us see an example using example using Esmerald and we will have:

* Three [models](./models.md):
    * User - From an [esmerald application][esmerald_application] `accounts`.
    * Customer - From an [esmerald application][esmerald_application] `customers`.
    * Product - From an [esmerald application][esmerald_application] `products`.
* Two [reflected models](./reflection/reflection.md):
    * Payment - From a payments table reflected from the existing database.
    * RecordView - From a SQL View reflected from the existing database.

And it will look like this:

<img src="https://res.cloudinary.com/tarsild/image/upload/v1691427229/packages/edgy/resources/reflected_cdc3rg.png" alt='Shell Example'>

Pretty cool, right? Then it is a normal python shell where you can import whatever you want and
need as per normal python shell interaction.

[esmerald_application]: https://esmerald.dev/management/directives/#create-app
