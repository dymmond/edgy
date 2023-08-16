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
[Django Tenants URL][django_tenants_url] (you didn't see this one coming, did you? 😜), Edgy
offers one **non-core** working solution for multi-tenancy.


[edgy]: ./edgy.md
[django_tenants]: https://django-tenants.readthedocs.io/en/latest/
[django_tenants_url]: https://django-tenants-url.tarsild.io/
