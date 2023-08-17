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

When a new tenant is created, upon the `save` of the record, it will create the schema with the
provided name in the creation of that same record.

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

The way the `TenantMixin` should be used is very simple.

```python hl_lines="3 9"
{!> ../docs_src/tenancy/contrib/tenant_mixin.py !}
```

### Domain

### TenantUser

## Example


[edgy]: ./edgy.md
[django_tenants]: https://django-tenants.readthedocs.io/en/latest/
[django_tenants_url]: https://django-tenants-url.tarsild.io/
