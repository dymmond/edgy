# Managers

The managers are a great tool that **Saffier** offers. Heavily inspired by Django, the managers
allow you to build unique tailored queries ready to be used by your models.

**Saffier** by default uses the the manager called `query` which it makes it simple to understand.

Let us see an example.

```python hl_lines="23 25"
{!> ../docs_src/models/managers/simple.py !}
```

When querying the `User` table, the `query` (manager) is the default and **should** be always
presented when doing it so.

### Custom manager

It is also possible to have your own custom managers and to do it so, you **should inherit**
the **Manager** class and override the `get_queryset()`.

For those familiar with Django managers, the principle is exactly the same. 😀

Let us now create new manager and use it with our previous example.

```python hl_lines="24 40 43 46 53"
{!> ../docs_src/models/managers/custom.py !}
```

These managers can be as complex as you like with as many filters as you desire. What you need is
simply override the `get_queryset()` and add it to your models.

### Override the default manager

Overriding the default manager is also possible by creating the custom manager and overriding
the `query` manager.

```python hl_lines="24 37 40 43 46"
{!> ../docs_src/models/managers/override.py !}
```

!!! Warning
    Be careful when overriding the default manager as you might not get all the results from the
    `.all()` if you don't filter properly.
