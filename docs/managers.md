# Managers

The managers are a great tool that **Edgy** offers. Heavily inspired by Django, the managers
allow you to build unique tailored queries ready to be used by your models.
Unlike in Django Managers are instance and class aware.
For every inheritance they are shallow copied and if used on an instance you have also an shallow copy you can customize.

Note: shallow copy means, deeply nested attributes or mutable attributes must be copied and not modified. As an alternative `__copy__` can be overwritten to do this for you.

**Edgy** by default uses the the manager called `query` for direct queries which it makes it simple to understand.
For related queries `query_related` is used which is by default a **RedirectManager** which redirects to `query`.

Let us see an example.

```python hl_lines="23 25"
{!> ../docs_src/models/managers/simple.py !}
```

When querying the `User` table, the `query` (manager) is the default and **should** be always
presented when doing it so.

## Inheritance

Managers can set the inherit flag to False, to prevent being used by subclasses. Things work like for fields.
An usage would be injected managers though we have non yet.

## Custom manager

It is also possible to have your own custom managers and to do it so, you **should inherit**
the **Manager** class and override the `get_queryset()`. For further customization it is possible to
use the **BaseManager** class which is more extensible.

For those familiar with Django managers, the concept is exactly the same. 😀

**The managers must be type annotated ClassVar** or an `ImproperlyConfigured` exception will be raised.

```python hl_lines="19"
{!> ../docs_src/models/managers/example.py !}
```

Let us now create new manager and use it with our previous example.

```python hl_lines="26 42 45 48 55"
{!> ../docs_src/models/managers/custom.py !}
```

These managers can be as complex as you like with as many filters as you desire. What you need is
simply override the `get_queryset()` and add it to your models.

## Override the default manager

Overriding the default manager is also possible by creating the custom manager and overriding
the `query` manager. By default the `query`is also used for related queries. This can be customized via setting
an explicit `query_related` manager.

```python hl_lines="26 39 42 45 48"
{!> ../docs_src/models/managers/override.py !}
```

Now with only overwriting the related manager:

```python hl_lines="26 39 42 45 48"
{!> ../docs_src/models/managers/override_related.py !}
```

!!! Warning
    Be careful when overriding the default manager as you might not get all the results from the
    `.all()` if you don't filter properly.
