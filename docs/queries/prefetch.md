# Prefetch Related

What is this thing of **prefetch**? Well, imagine you want to get a record from the database and at the same time you also want to get the nested models related to that same model as well.

The prefetch does this job for you, in other words, pre-loads the related models.

Django for example has the `prefetch_related` as well and Edgy has a similar approach to the problem but faces it in a different and more clear way.

The **Edgy** way of doing it its by also calling the `prefetch_related` queryset but passing [Prefetch](#prefetch) instances and utilising the [related_name](./related-name.md) to do it so.

Note:

The syntax is like the django syntax. With `__` a foreign key or related name of a foreign key is traversed. Only the last part of the path must be a inversion of a foreign key (`related_name`).

Note:

this kind of traversal for foreign keys is new. Former versions used the `related_name` of foreign keys with the effect that a model could only specify a related_name once despite on a different ForeignKey.

Note:

ManyToMany fields create a through model which must be traversed.

## Prefetch

The main object used for the `prefetch_related` query. This particular object contains a set of instructions that helps mapping the results with the given returned object.

```python
from edgy import Prefetch
```

Or

```python
from edgy.core.db.querysets import Prefetch
```

### Parameters

To make the [Prefetch](#prefetch) work properly some parameters are needed to make sure it runs smoothly:

* **related_name** - The [related_name](./related-name.md) type of query to perform.
* **to_attr** - The name of the new attribute in the model being queried where the results will be stored.
* **queryset** (Optional) - Additional queryset for the type of query being made.

### Special attention

This means, imagine you have the following:

```python
{!> ../docs_src/prefetch/second/models.py !}
```

We have now three [related names](./related-name.md):

* **companies** - ForeignKey in `Company` model.
* **studios** - ForeignKey in `Studio` model.
* **tracks** - ForeignKey in `Track` model.

**Add some data into it**

```python
{!> ../docs_src/prefetch/second/data.py !}
```

**You know want to query**:

* All the tracks that belong to a specific `Company`. The tracks are associated with `albums` and `studios`.

```python hl_lines="33-35"
{!> ../docs_src/prefetch/second/prefetch.py !}
```

The [Prefetch](#prefetch) used the foreign key name and the `related_name` at the last part to perform the query and did the transversal approach.

The `company` now has an attribute `tracks` where it contains all the associated `tracks` list.

### Auto generated related names

What if you don't add a `related_name`? That is covered in [related_names](./related-name.md#auto-generating) related with the [auto generation](./related-name.md#auto-generating) of the related name, which means, if you don't provide a related name, **automatically Edgy generates it and that is the one you must use**.

### What can be used

The way you do [queries](./queries.md) remains exactly the same you do all the time with **Edgy** as the [Prefetch](#prefetch) is another process running internally, so that means you can apply any filter you want as you would normal do in a query.

### How to use

Now its where the good stuff starts. How can you take advantage of the `Prefetch` object in your queries.

Let us assume we have three models:

1.  User
2.  Post
3.  Article

Something like this.

```python
{!> ../docs_src/prefetch/first/models.py !}
```

!!! Note
    For example purposes, the connection string will be to SQLite and the models quite simple but enough for this.

We now want to create some posts and some articles and associate to the `user`. Something like this:

```python
{!> ../docs_src/prefetch/first/data.py !}
```

!!! Note
    We simply want to generate posts and articles just to have data for the queries.

#### Using Prefetch

With all the data generated for the models, we now want to query:

* All the users in the system.
* All the posts associated to each user.
* All the articles associated to each user.

```python hl_lines="33-36"
{!> ../docs_src/prefetch/first/prefetch.py !}
```

You can confirm all the data by simply asserting it.

```python
{!> ../docs_src/prefetch/first/asserting.py !}
```

#### Using the queryset

What if you want to use the `queryset` parameter of the [Prefetch](#prefetch). Let us use the same [example of before](#special-attention).

```python
{!> ../docs_src/prefetch/second/models.py !}
```

**Add some data into it**

```python
{!> ../docs_src/prefetch/second/data.py !}
```

**You know want to queryusing the queryset**:

* All the tracks that belong to a specific `Company`. The tracks are associated with `albums` and `studios` **but** the `Track` will be also internally filtered.

```python hl_lines="14"
{!> ../docs_src/prefetch/second/prefetch_filtered.py !}
```

This easy, right? The total tracks should be **1** as the **bird** is part of the title of the `track` that belongs to the `studio` that belongs to the `company`.
```
