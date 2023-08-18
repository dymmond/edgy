# Contrib

If you are not familiar with the concept of multi-tenancy, have a look at the [previous section][edgy]
and have a read.

We all have suffered from concepts of design and undeerstanding in fact what is multi-tenancy
and how to imlpement the right solution.

The real answer here is that **there is no real one only working solution** for multi-tenancy
applications. Everything depends of your needs but there are approaches to the problem.

1. **Shared schemas** - The data of all users are shared within the same schema and filtered by common IDs or whatever that is unique to the platform.
This is not so great for GDPR (Europe) or similar in different countries.
2. **Shared database, different Schemas** - The user's data is split by different schemas but live on the same database.
3. **Different databases** - The user's data or any data live on different databases.

**Edgy** to simplify your life of development offers an out-of-the-box solution for multi-tenancy
using the second approach, ***shared database, different schemas*** as this is more common to be
applied for majority of the applications.

The `contrib` of Edgy is not related to its core, although it uses components from it for obvious
reasons, it works as possible alternative that can be used by you **but it is not mandatory to do it**
as you can have your own design.

Heavily inspired by [Django Tenants][django_tenants] and from the same author of
[Django Tenants URL][django_tenants_url] and **Edgy** (you didn't see this one coming, did you? 😜), Edgy
offers one **non-core** working solution for multi-tenancy.

!!! Warning
    **Edgy** supports one database migrations only which internally uses alembic for it. As of now,
    there are no support for multi-tenancy templates for migrations so that would need to be
    manually added and managed by you.

What does this non-core multi-tenancy brings?

* Models to manage the tenants and the links between the tenants and users.
* Automatic schema generation up the creation of a tenant in the tenants table.
* **Settings object needed to use the module**

## Brief explanation

The module works as an *independent* application inside Edgy but using the obvious core components.

The module uses a [settings file](#settings) that inherits from the main [settings](../settings.md)
module of **Edgy** which means you would only needed to override the needed values and use it.

Every model that required to be applied on a `tenant` (schema) level, you require to inherit from
the [TenantModel](#tenantmodel) and pass the `is_tenant=True` parameter in the `Meta` class.

To use this module, you will need to have your [EDGY_SETTINGS_MODULE](../settings.md#edgy_settings_module)
set as well. More on this in the [TenancySettings](#tenancysettings).

More on this in the [example](#example) provided.

## Imports

All the needed imports are located inside the `multi_tenancy` module in `contrib`:

```python
from edgy.contrib.multi_tenancy import TenantModel. TenantRegistry, TenancySettings
from edgy.contrib.multi_tenancy.models import TenantMixin, DomainMixin, TenantUserMixin
```

## TenantModel

This is the base of all models that **require the table to be created inside the newly created schema**.

The `TenantModel` already inherits from the base `edgy.Model` which means it will apply all the needed
core functionalities but introduces a new internam `metaclass` required for the `is_tenant` attribute.

```python hl_lines="2 5 8 19"
{!> ../docs_src/tenancy/contrib/tenant_model.py !}
```

This is how you **must** declare a model that you want it to be in your multi-tenant schemas using
this particular module. **This is mandatory**.

Did you notice that a `TenantRegistry` was used? Nothing to worry about, it is nothing completely
new to you, it is just an inherited [registry](../registry.md) with extra properties specifically
created for this purpose 😁.

## TenantRegistry

The `TenantRegistry` as mentioned above, it is just an inherited [registry](../registry.md) with extra properties specifically
created for the purpose of useing the Edgy contrib module where it adds some extras to make this
integration easier, such as the `tenant_models` object which is internally used to understand
which models should be generated upon the creation of a `Tenant` automatically.

```python hl_lines="2 5 8 19"
{!> ../docs_src/tenancy/contrib/tenant_registry.py !}
```

## TenancySettings

Now, this object is **extremely important**. This settings object inherits from the default
[settings](../settings.md) and adds the extra needed attributes that are used by the provided
[model mixins](#model-mixins).

Now there are two ways that you can approach this.

1. **You have your own settings with the following properties added**:

    * `auto_create_schema: bool = True` - Used by the [Tenant](#tenant) model.
    * `auto_drop_schema: bool = False` - Used by the [Tenant](#tenant) model.
    * `tenant_schema_default: str = "public"` - Used by the [Domain](#domain) model.
    * `tenant_model: Optional[str] = None` - Used by the [TenantUser](#tenantuser) model.
    * `domain: Any = os.getenv("DOMAIN")` - Used by the [Tenant](#tenant) model.
    * `domain_name: str = "localhost"` - Used by the [Domain](#domain) model.
    * `auth_user_model: Optional[str] = None` - Used by the [TenantUser](#tenantuser) model.

2. **You inherit the `TenancySettings` object and override the values needed and use it as your [EDGY_SETTINGS_MODULE](../settings.md#edgy_settings_module)**.

    ```python
    from edgy.contrib.multi_tenancy import TenancySettings
    ```

Choose whatver it suits your needs better 🔥.

## Model Mixins

Edgy contrib uses specifically tailored models designed to run some operations for you like the
[Tenant](#tenant) creating the schemas when a record is added or dropping them when it is removed.

These are model mixins and the reason why it is called mixins it is because they are `abstract` and
**must be inherited** by your own models.

!!! Tip
    By default, the contrib model mixins have the meta flag `is_tenant` set to `False` because in
    theory these are the ones that will be managing all your application tenants. Unless you
    specifically specify to be `True`, they will be ignored from every schema besides the main
    `shared` or `public`.

### Tenant

This is the main model that manages all the tenants in the system using the Edgy contrib module.

When a new tenant is created, upon the `save` of the record, **it will create the schema with the provided name in the creation of that same record.**

**Fields**

* **schema_name** - Unique for the new schema. **Mandatory**.
* **domain_url** - Which domain URL the schema should be associated. **Not mandatory**.
* **tenant_name** - Unique name of the tenant. **Mandatory**.
* **tenant_uuid** - Unique UUID (auto generated if not provided) of the tenant.

    <sup>Default: `uuid.uuid4()`</sup>

* **paid_until** - If the tenant is on a possible paid plan/trial. **Not mandatory**.
* **on_trial** - Flag if the tenant is on a possible trial period.

    <sup>Default: `True`</sup>

* **created_on** - The date of the creation of the tenant. If nothing is provided, it will automatically generate it.

    <sup>Default: `datetime.date()`</sup>


#### How to use it

The way the `TenantMixin` should be used it is very simple.

```python hl_lines="3 9"
{!> ../docs_src/tenancy/contrib/tenant_mixin.py !}
```

### Domain

This is a simple model that can be used but it is not mandatory. Usually when referring to multi-tenancy
means different domains (or subdomains) for specific users and those domains are also associated
with a specific tenant.

The domain table it is the place where that information is stored.

**Fields**

* **domain** - Unique domain for the specific associated tenant. **Mandatory**.
* **tenant** - The foreign key associated with the newly created tenant (or existing tenant). **Mandatory**.
* **is_primary** - Flag indicating if the domain of the tenant is the primary or othwerise.

    <sup>Default: `True`</sup>

#### How to use it

The way the `DomainMixin` should be used it is very simple.

```python hl_lines="3 18"
{!> ../docs_src/tenancy/contrib/domain_mixin.py !}
```

### TenantUser

Now this is a special table. This table was initially created and designed for the
[Django Tenants URL][django_tenants_url] approach and aimed to help solving the multi-tenancy on a
path level, meaning, instead of checking for subdomains for a tenant, it would look at the URL path
and validate the user from there.

This is sometimes referred and `sub-folder`. Django Tenants recently decided to also solve that
problem natively and the same author of Edgy and Django Tenants URL offer to donate the package to
the main package since it does solve that problem already.

For that reason, it was decided to also provide the same level of support in this contrib approach
as this is a wide use case for a lot of companies with specific levels of security and infrastructure
designs.

**Fields**

* **user** - Foreign key to the user. This is where the `settings.auth_user_model` is used. **Mandatory**.
* **tenant** - Foreign key to the tenant. This is where the `settings.tenant_model` is used. **Mandatory**.
* **is_active** - Flag indicating if the tenant associated with the user in the `TenantUser` model is active or not.

    <sup>Default: `False`</sup>
* **created_on** - Date of the creation of the record. Automatically generates if nothing is provided.

#### How to use it

The way the `DomainMixin` should be used it is very simple.

```python hl_lines="3 27"
{!> ../docs_src/tenancy/contrib/tenant_user_mixin.py !}
```

## Example

Well with all the models and explanations covered, is time to create a practical example where all
of this is applied, this way it will make more sense to understand what is what and how everything
works together 🔥.

For this example we will be using [Esmerald][esmerald] and [Esmerald middleware][esmerald_middleware]
with Edgy. We will be also be creating:

* [Tenant](#tenant)
* [Domain](#domain)
* [TenantUser](#tenantuser)
* [Settings](#tenancysettings)

All of this will come together and in the end an [Esmerald][esmerald] API with middleware and an
endpoint will be the final result.

### Create the initial models

Let us create the initial models where we will be storing tenant information among other things.

```python title="models.py"
{!> ../docs_src/tenancy/contrib/example/models.py !}
```

So, so far some models were created just for this purpose. You will notice that two different
user models were created and that is intentional.

The main reason for those two different models it is because we might want to have speific users
for specific `schemas` for different application access level purposes as well as the `system` users
where the `tenant` is checked and mapped.

### Create the TenancySettings

With all the models defined, we can now create our [TenancySettings](#tenancysettings) objects
and make it available to be used by **Edgy**.

The settings can be stored in a location like `myapp/configs/edgy/settings.py`

```python title="settings.py"
{!> ../docs_src/tenancy/contrib/example/settings.py !}
```

**Make the settings globally available to Edgy**.

```shell
$ export EDGY_SETTINGS_MODULE=myapp.configs.edgy.settings.EdgySettings
```

Exporting as an environment variable will make sure Edgy will use your settings instead of the
default one. You don't need to worry about the default settings as the `TenancySettings` inherits
all the default settings from Edgy.

### Create the middleware

Now this is where the things start to get exciting. Let us create the middleware that will check
for the tenant and automatically set the tenant for the user.

!!! danger
    The middleware won't be secure enough for production purposes. Don't use it directly
    like this. Make sure you have your own security checks in place!

The middleware will be very simple as there is no reason to complicate for this example.

The `TenantMiddleware` will be only reading from a given header `tenant` and match that tenant
against a `TenantUser`. If that tenant user exists, then sets the global application tenant
to the found one, else ignores it.

Because we won't be implementing any `authentication` system in this example where Esmerald has a lot
of examples that can be checked in the docs, we will be also passing an `email` in the header just
to run some queries against.

Simple right?

```python title="middleware.py"
{!> ../docs_src/tenancy/contrib/example/middleware.py !}
```

As mentioned in the comments of the middleware, it reads the `tenant` and `email` from the headers
and uses it to run the queries against the database records and if there is a relationship between `User` and `Tenant` in the
`TenantUser`, it will use the `set_tenant` to set the global tenant for the user calling the APIs.

### Create some mock data

Not it is time to create some mock data to use it later.

```python title="mock_data.py"
{!> ../docs_src/tenancy/contrib/example/mock_data.py !}
```

#### What is happening

In fact it is very simple:

1. Creates two global users (no schema associated).
2. Creates a [Tenant](#tenant) for `edgy`. As mentioned above, when a record is created, it will automatically
generate the `schema` and the corresponding tables using the `schema_name` provided on save.
3. Creates a `HubUser` (remember that table? The one that only exists inside each generated schema?) using
the newly `edgy` generated schema.
4. Creates a relation `TenantUser` between the global user `edgy` and the newly `tenant`.
5. Adds products on a schema level for the `edgy` user specific.
6. Adds products to the global user (no schema associated) `John`.

### Create the API

Now it is time to create the Esmerald API that will **only** read the products associated with
the user that it is querying it.

```python title="api.py"
{!> ../docs_src/tenancy/contrib/example/api.py !}
```

### The application

Now it is time to actually assemble the whole application and plug the middleware.

```python title="api.py"
{!> ../docs_src/tenancy/contrib/example/app.py !}
```

And this should be it! We now have everything we want and need to start querying our products from
the database. Let us do it then!

#### Run the queries

Let us use the `httpx` package since it is extremely useful and simple to use. Feel free to choose
any client you prefer.

```python title="api.py"
{!> ../docs_src/tenancy/contrib/example/queries.py !}
```

And it should be pretty much it 😁. Give it a try with your own models, schemas and data. Have fun
with this out-of-the-box multi-tenancy approach.

### Notes

As mentioned before, Edgy does not suppor yet multi-tenancy migrations templates. Although the
migration system uses alembic under the hood, the multi-tenant migrations **must be managed by you**.

The contrib upon the creation of a tenant, it will generate the tables and schema for you based on
what is already created in the `public` schema but if there is any change to be applied that must
be carefully managed by you from there on.


[edgy]: ./edgy.md
[esmerald]: https://esmerald.dev
[esmerald_middleware]: https://esmerald.dev/middleware
[django_tenants]: https://django-tenants.readthedocs.io/en/latest/
[django_tenants_url]: https://django-tenants-url.tarsild.io/
