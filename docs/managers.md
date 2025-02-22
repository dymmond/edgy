# Managers

Managers are a powerful feature in **Edgy**, heavily inspired by Django's manager system. They allow you to create tailored, reusable query sets for your models. Unlike Django, Edgy managers are instance and class aware. For every inheritance, they are shallow copied, and if used on an instance, you also have a shallow copy that you can customize.

**Note:** Shallow copy means that deeply nested or mutable attributes must be copied, not modified. Alternatively, you can override `__copy__` to handle this for you.

**Edgy** uses the `query` manager by default for direct queries, which simplifies understanding. For related queries, `query_related` is used, which is a **RedirectManager** by default that redirects to `query`.

Let's look at a simple example:

```python hl_lines="23 25"
{!> ../docs_src/models/managers/simple.py !}
```

When querying the `User` table, the `query` manager is the default and **should** always be present.

## Inheritance

Managers can set the `inherit` flag to `False` to prevent subclasses from using them. This is similar to how fields work. This is useful for injected managers, though we don't have any yet.

## Custom Managers

You can create your own custom managers by **inheriting** from the **Manager** class and overriding the `get_queryset()` method. For more extensive customization, you can use the **BaseManager** class, which is more extensible.

For those familiar with Django managers, the concept is exactly the same. 😀

**Managers must be type annotated as ClassVar**, or an `ImproperlyConfigured` exception will be raised.

```python hl_lines="19"
{!> ../docs_src/models/managers/example.py !}
```

Let's create a new manager and use it with our previous example:

```python hl_lines="26 42 45 48 55"
{!> ../docs_src/models/managers/custom.py !}
```

These managers can be as complex as you like, with as many filters as you need. Simply override `get_queryset()` and add the manager to your models.

## Overriding the Default Manager

You can override the default manager by creating a custom manager and overriding the `query` manager. By default, `query` is also used for related queries. This can be customized by setting an explicit `query_related` manager.

```python hl_lines="26 39 42 45 48"
{!> ../docs_src/models/managers/override.py !}
```

Now, let's override only the related manager:

```python hl_lines="26 39 42 45 48"
{!> ../docs_src/models/managers/override_related.py !}
```

!!! Warning
    Be careful when overriding the default manager, as you might not get all the results from `.all()` if you don't filter properly.

## Key Concepts and Benefits

* **Reusability:** Managers allow you to encapsulate complex query logic and reuse it across your application.
* **Organization:** They help keep your model definitions clean and organized by moving query logic out of the model class.
* **Customization:** You can create managers that are tailored to the specific needs of your models.
* **Instance and Class Awareness:** Edgy managers are aware of the instance and class they are associated with, allowing for more dynamic and context-aware queries.
* **Inheritance Control:** The `inherit` flag allows you to control whether managers are inherited by subclasses.
* **Separation of Concerns:** Managers allow you to separate query logic from model definitions, leading to cleaner and more maintainable code.

## Use Cases

* **Filtering by Status:** Create a manager that only returns active records.
* **Ordering by Specific Fields:** Create a manager that returns records ordered by a specific field or set of fields.
* **Aggregations:** Create a manager that performs aggregations on your data, such as calculating averages or sums.
* **Complex Joins:** Create a manager that performs complex joins between multiple tables.
* **Custom Query Logic:** Create a manager that implements custom query logic that is specific to your application.

By using managers effectively, you can create more powerful and maintainable Edgy applications.
