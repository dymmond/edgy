# Queries

Making queries is a must when using an ORM and being able to make complex queries is even better
when allowed.

SQLAlchemy is known for its performance when querying a database and it is very fast. The core
being part of **Edgy** also means that edgy performs extremely well when doing it.

When making queries in a [model][model], the ORM uses the [managers][managers] to
perform those same actions.

If you haven't yet seen the [models][model] and [managers][managers] section, now would
be a great time to have a look and get yourself acquainted.

## QuerySet

When making queries within Edgy, this return or an object if you want only one result or a
`queryset` which is the internal representation of the results.

If you are familiar with Django querysets, this is **almost** the same and by almost is because
edgy restricts loosely queryset variable assignments.

Let us get familar with queries.

Let us assume you have the following `User` model defined.

```python
{!> ../docs_src/queries/model.py !}
```

As mentioned before, Edgy returns queysets and simple objects and when queysets are returned
those can be chained together, for example, with `filter()` or `limit()`.

```python
await User.query.filter(is_active=True).filter(first_name__icontains="a").order_by("id")
```

Do we really need two filters here instead of one containing both conditions? No, we do not but
this is for example purposes.

Internally when querying the model and with returning querysets, **Edgy** runs the `all()`.
This can be done manually by you or automatically by the ORM.

Let us refactor the previous queryset and apply the manual `all()`.

```python
await User.query.filter(is_active=True, first_name__icontains="a").order_by("id").all()
```

And that is it. Of course there are more filters and operations that you can do with the ORM and
we will be covering that in this document but in a nutshell, querying the database is this simple.

## Selecting the database and schema

By default the default schema and the default database is used. These are the `db_schema` and the `database` attributes of the registry.
We can use different databases and schemas by using:

`using(*, schema, database)`

This method allows us to select a database specified in registry extra via its name or even an arbitary database object.

For schema it is valid to use a string for a schema, None for the main schema or False to reset to the current default schema.

It is the merge of the former methods `using` (with a positional argument) and `using_with_db` which are still valid but deprecated and have usability problems.


### Using with `with_schema`

This is an **alternative** to `[using](#selecting-the-database-and-schema)` and serves solely as the purpose of avoiding
writing all the time `Model.query.using(...)`.

You can use `with_schema(...)` to tell the query to always query
a specific schema within the context, in other words, using the `with_schema()` you don't need to constantly
write `using(...)`.

Importing is as simple as this:

```python
from edgy.core.db import with_schema
```

Let us see an example:

**With the classic .using()**

```python
# Using the 'main' schema

User.query.using(schema='main').all()
User.query.using(schema='main').filter(email__icontains="user@example.com")
User.query.using(schema='main').get(pk=1)
```

**Using the with_schema**

```python
# Using the 'main' schema
with with_schema("main"):

    # Query the 'User' from the 'main' schema
    User.query.all()
    User.query.filter(email__icontains="user@example.com")
    User.query.get(pk=1)
```

There is also a method called `set_schema` which returns a reset token:

**Using the set_schema**

```python
# Using the 'main' schema
token = set_schema("main"):

try:
    # Query the 'User' from the 'main' schema
    User.query.all()
    User.query.filter(email__icontains="user@example.com")
    User.query.get(pk=1)
finally:
    token.var.reset(token)
```


!!! Warning
    There were 2 old methods: `activate_schema`, `deactivate_schema`.
    Their use is not recommended as they don't enforce a scope.

## Load the foreign keys beforehand with select related

Select related is a functionality that *follows the foreign-key relationships* by selecting any
additional related object when a query is executed. You can imagine it as a classic `join`.

The difference is that when you execute the [select_related](../relationships.md#load-an-instance-with-the-foreign-key-relationship-on-it-with-select-related),
the foreign keys of the model being used by that operation will be opulated with the database results.

You can use the classic [select_related](../relationships.md#load-an-instance-with-the-foreign-key-relationship-on-it-with-select-related):

```python
await Profile.query.select_related("user").get(id=1)
```

Or you can use the `load()` function of the model for the foreign key. Let us refactor the example above.

```python
profile = await Profile.query.get(id=1)
await profile.user.load()
```

The `load()` works on any foreign key declared and it will automatically load the data into that
field.

## Returning querysets

There are many operations you can do with the querysets and then you can also leverage those for
your use cases.

### Exclude

The `exclude()` is used when you want to filter results by excluding instances.

```python
users = await User.query.exclude(is_active=False)
```

### Exclude secrets

The `exclude_secrets()` is used when you want to exclude (reinclude) fields with the secret attribute.

```python
users = await User.query.exclude_secrets()
```

Or to reinclude:

```python
users = await User.query.exclude_secrets().exclude_secrets(False)
```

### Batch size

When iterating it is sometimes useful to set the batch size. By default (or when providing None) the default of databasez is used.

Note: this is just for tweaking memory usage/performance when using iterations and has currently no user visible effect.

```python
async for user in User.query.batch_size(30):
    pass
```


### Filter

#### Django-style

These filters are the same **Django-style** lookups.

```python
users = await User.query.filter(is_active=True, email__icontains="gmail")
```

The same special operators are also automatically added on every column.

* **in** - SQL `IN` operator.
* **exact** - Filter instances matching the exact value.
* **iexact** - Filter instances mathing the exact value but case-insensitive.
* **contains** - Filter instances that contains a specific value.
* **icontains** - Filter instances that contains a specific value but case-insensitive.
* **lt** - Filter instances having values `Less Than`.
* **lte** - Filter instances having values `Less Than Equal`.
* **gt** - Filter instances having values `Greater Than`.
* **gte** - Filter instances having values `Greater Than Equal`.


##### Example

```python
users = await User.query.filter(email__icontains="foo")

users = await User.query.filter(id__in=[1, 2, 3])
```

##### Using `Q` or other boolean clauses outside of filter

`Q` is in fact the same like `and_` of edgy (alias). It is a helper for django users, which are used to `Q`.
It can be used to combine where clauses outside of the `filter` function.

Note: the `or_` c which differs in this way, that it blocks when empty instead of allowing all.

###### Example:

```python
from edgy import and_, or_, Q
# only valid with edgy Q() or and_()
q = Q()
# returns results
User.query.filter(q)
q &= and_(User.columns.name == "Edgy")
# returns Users named Edgy
User.query.filter(q)
# only valid with edgy or_
q = or_()
# returns nothing
User.query.filter(q)
q &= Q(User.columns.name == "Edgy")
# returns Users named Edgy
User.query.filter(q)
```

#### SQLAlchemy style

Since Edgy uses SQLAlchemy core, it is also possible to do queries in SQLAlchemy style.
The filter accepts also those.

##### Example

```python
users = await User.query.filter(User.columns.email.contains("foo"))

users = await User.query.filter(User.columns.id.in_([1, 2, 3]))
```

!!! Warning
    The `columns` refers to the columns of the underlying SQLAlchemy table.

!!! Warning
    This works only for the main model of a QuerySet. Related are handled via `f"{hash_tablkey(tablekey=model.table.key, prefix=...)}_{columnkey}"`.
    You can pass the column via `sqlalchemy.column` (lowercase column).

All the operations you would normally do in SQLAlchemy syntax, are allowed here.

##### Using  `and_` and `or_` with kwargs

Often you want to check against an dict of key-values which should all match.
For this there is an extension of edgy's `and_` and `or_` which takes a model or columns and
matches kwargs against:

```python
users = await User.query.filter(and_.from_kwargs(User, name="foo", email="foo@example.com"))
# or

users = await User.query.filter(and_.from_kwargs(User, **my_dict))
```

#### OR

Edgy QuerySet can do global ORs. This means you can attach new OR clauses also later.

```python
# actually and_ is a synonym for filter
user_query = User.query.and_(active=True).or_(email="gmail")
user_query._or(email="outlook")
# active users with email gmail or outlook are retrieved
users = await user_query
```

Note: when passing multiple clauses to `or_` a local OR is executed instead.
Because of the broad scope this is only recommended for simple queries.

You can do instead something like:

```python
# actually and_ is a synonym for filter
user_query = User.query.and_(active=True)
# add a local or
user_query = user_query.or_({"email": "outlook"}, {"email": "gmail"})
# active users with email gmail or outlook are retrieved
users = await user_query
```

or pass querysets:

```python
# actually and_ is a synonym for filter
user_query = User.query.and_(active=True)
user_query = user_query.or_(user_query, {"email": "outlook"}, {"email": "gmail"})
# active users or users with email gmail or outlook are retrieved
users = await user_query
```

##### Passing multiple keyword based filters

You can also passing multiple keyword based filters by providing them as a dictionary

```python
user_query = User.query.or_({"active": True}, {"email": "outlook"}, {"email": "gmail"}).
# active users or users with email gmail or outlook are retrieved
users = await user_query
```
##### Local only OR

If the special mode of or_ is not wanted there is a function named `local_or`. It is similar
to the or_ function except it doesn't have the global OR mode.

### Limit

Limiting the number of results. The `LIMIT` in SQL.

```python
users = await User.query.limit(1)

users = await User.query.filter(email__icontains="foo").limit(2)
```

### Offset

Applies the office to the query results.

```python
users = await User.query.offset(1)

users = await User.query.filter(is_active=False).offset(2)
```

Since you can chain the querysets from other querysets, you can aggregate multiple operators in one
go as well.

```python
await User.query.filter(email__icontains="foo").limit(5).order_by("id")
```

### Order by

Classic SQL operation and you need to order results. Prefix with `-` to get a descending order.


**Order by descending id and ascending email**

```python
users = await User.query.order_by("email", "-id")
```

**Order by ascending id and ascending email**

```python
users = await User.query.order_by("email", "id")
```

### Reverse

Reverse the order. Flip `-` prefix of order components.

### Lookup

This is a broader way of searching for a given term. This can be quite an expensive operation so
**be careful when using it**.

```python
users = await User.query.lookup(term="gmail")
```

### Distinct

Applies the SQL `DISTINCT ON` on a table if it has arguments otherwise a plain `DISTINCT`.

```python
users = await User.query.distinct("email")
```

!!! Warning
    Not all the SQL databases support the `DISTINCT ON` fields equally, for example, `mysql` has
    has that limitation whereas `postgres` does not.
    Be careful to know and understand where this should be applied.
    You can mitigate this by providing no argument (filter applies on all columns).


### Select related

Returns a QuerySet that will “follow” foreign-key relationships, selecting additional
related-object data when it executes its query.

This is a performance booster which results in a single more complex query but means

later use of foreign-key relationships won’t require database queries.

A simple query:

```python
profiles = await Profile.query.select_related("user")
```

Or adding more operations on the top

```python
profiles = await Profile.query.select_related("user").filter(email__icontains="foo").limit(2)
```

## Returning results

### All

Copy the queryset except caches.

```python
users = await User.query.all()
```

!!! Tip
    The all as mentioned before it automatically executed by **Edgy** if not provided and it
    can also be aggregated with other [queryset operations](#returning-querysets).

!!! Tip
    For flushing the queryset caches instead provide True as argument. This mutates the queryset.

### Save

This is a classic operation that is very useful depending on which operations you need to perform.
Used to save an existing object in the database. Slighly different from the [update](#update) and
simpler to read.

```python
await User.query.create(is_active=True, email="foo@bar.com")

user = await User.query.get(email="foo@bar.com")
user.email = "bar@foo.com"

await user.save()
# or as explicit parameter
await user.save(values={"email": "sky@example.com"})
```


Now a more unique, yet possible scenario with a save. Imagine you need to create an exact copy
of an object and store it in the database. These cases are more common than you think but this is
for example purposes only.

```python
await User.query.create(is_active=True, email="foo@bar.com", name="John Doe")

user = await User.query.get(email="foo@bar.com")
# User(id=1)

# Making a quick copy
user.id = None
new_user = await user.save()
# User(id=2)
```

#### Parameters

`save` has following signature:

`save(force_insert=False,values=None)`

What they do is:

- `force_insert` (former `force_save`): Instead of conditionally updating, force an insert.
- `values`: Overwrite values explicitly. Values specified here are marked as explicit set parameters.

### Update

Models have an `update` method too. It enforces updates:

```python
await User.query.create(is_active=True, email="foo@bar.com")

user = await User.query.get(email="foo@bar.com")

await user.update(email="bar@example.com")
```

### Create

Used to create model instances.

```python
await User.query.create(is_active=True, email="foo@bar.com")
await User.query.create(is_active=False, email="bar@foo.com")
await User.query.create(is_active=True, email="foo@bar.com", first_name="Foo", last_name="Bar")
```

Create takes `ModelRef`s as positional arguments to automatically evaluate and stage them.

### Delete

Used to delete an instance.

```python
await User.query.filter(email="foo@bar.com").delete()
```

Or directly in the instance.

```python
user = await User.query.get(email="foo@bar.com")

await user.delete()
```


#### Parameters

- `use_models`: Instead of deleting directly in db, models are queried and deleted one by one. It is automatically activated in case of
                file fields (or other fields with a post_delete_callback method).

### Update

You can update model instances by calling this operator.


```python
await User.query.filter(email="foo@bar.com").update(email="bar@foo.com")
```

Or directly in the instance.

```python
user = await User.query.get(email="foo@bar.com")

await user.update(email="bar@foo.com")
```

Or not very common but also possible, update all rows in a table.

```python
user = await User.query.update(email="bar@foo.com")
```

### In-database updates

For most fields it is possible to do something like

``` python
await User.query.update(balance=User.table.columns.balance - 10)
```

This updates the value directly in db without roundtrip.
In multi column fields or heavily customized fields like ForeignKeys this may not work.

Why do I need this?

This is a race-free way to update values. Suppose you want to update the balance of a customer.
This allows to update it without worrying about concurrency.


!!! Warning
    Here exist no temporary model instances. This implies neither pre_save_callback/post_save_callback hooks are called nor to_model is executed before.
    Data is passed to clean rawly.

### Get

Obtains a single record from the database.

```python
user = await User.query.get(email="foo@bar.com")
```

You can mix the queryset returns with this operator as well.

```python
user = await User.query.filter(email="foo@bar.com").get()
```

### First

When you need to return the very first result from a queryset.

```python
user = await User.query.first()
```

You can also apply filters when needed.

### Last

When you need to return the very last result from a queryset.

```python
user = await User.query.last()
```

You can also apply filters when needed.

### Exists

Returns a boolean confirming if a specific record exists.

```python
exists = await User.query.filter(email="foo@bar.com").exists()
```

### Contains

Returns true if the QuerySet contains the provided object.

```python
user = await User.query.create(email="foo@bar.com")

exists = await User.query.contains(instance=user)
```


### Count

Returns an integer with the total of records.

```python
total = await User.query.count()
```
### Values

Returns the model results in a dictionary like format.

```python
await User.query.create(name="John" email="foo@bar.com")

# All values
user = User.query.values()
users == [
    {"id": 1, "name": "John", "email": "foo@bar.com"},
]

# Only the name
user = User.query.values("name")
users == [
    {"name": "John"},
]
# Or as a list
# Only the name
user = User.query.values(["name"])
users == [
    {"name": "John"},
]

# Exclude some values
user = User.query.values(exclude=["id"])
users == [
    {"name": "John", "email": "foo@bar.com"},
]
```

The `values()` can also be combined with `filter`, `only`, `exclude` as per usual.

**Parameters**:

* **fields** - Fields of values to return.
* **exclude** - Fields to exclude from the return.
* **exclude_none** - Boolean flag indicating if the fields with `None` should be excluded.

### Values list

Returns the model results in a tuple like format.

```python
await User.query.create(name="John" email="foo@bar.com")

# All values
user = User.query.values_list()
users == [
    (1, "John" "foo@bar.com"),
]

# Only the name
user = User.query.values_list("name")
users == [
    ("John",),
]
# Or as a list
# Only the name
user = User.query.values_list(["name"])
users == [
    ("John",),
]

# Exclude some values
user = User.query.values(exclude=["id"])
users == [
    ("John", "foo@bar.com"),
]

# Flattened
user = User.query.values_list("email", flat=True)
users == [
    "foo@bar.com",
]
```

The `values_list()` can also be combined with `filter`, `only`, `exclude` as per usual.

**Parameters**:

* **fields** - Fields of values to return.
* **exclude** - Fields to exclude from the return.
* **exclude_none** - Boolean flag indicating if the fields with `None` should be excluded.
* **flat** - Boolean flag indicating the results should be flattened.

### Only

Returns the results containing **only** the fields in the query and nothing else.

```python
await User.query.create(name="John" email="foo@bar.com")

user = await User.query.only("name")
```

!!! Warning
    You can only use `only()` or `defer()` but not both combined or a `QuerySetError` is raised.

### Defer

Returns the results containing all the fields **but the ones you want to exclude**.

```python
await User.query.create(name="John" email="foo@bar.com")

user = await User.query.defer("name")
```

!!! Warning
    You can only use `only()` or `defer()` but not both combined or a `QuerySetError` is raised.

### Get or none

When querying a model and do not want to raise a [ObjectNotFound](../exceptions.md#objectnotfound) and
instead returns a `None`.

```python
user = await User.query.get_or_none(id=1)
```

### Convert to select expression

Sometimes you want directly work with a sqlalchemy select expression. This is possible via
`as_select`:

```python
user_select = await User.query.filter(id=1).as_select()
```

## Using the cache

`first`, `last`, `count` are always cached and also initialized when iterating over the query or requesting all results.
Other functions which take keywords to filter can use the cache
by providing the filters as keywords or leave all arguments empty.
Some functions like `contains` exploit this by rewriting its query.

For clearing the cache, `all` can be used:

```python
users = User.query.all().filter(name="foobar")
# clear the cache
users.all(True)
await users
```

## Useful methods

### Get or create

When you need get an existing model instance from the matching query. If exists, returns or creates
a new one in case of not existing.

Returns a tuple of `instance` and boolean `created`.

```python
user, created = await User.query.get_or_create(email="foo@bar.com", defaults={
    "is_active": False, "first_name": "Foo"
})
```

This will query the `User` model with the `email` as the lookup key. If it doesn't exist, then it
will use that value with the `defaults` provided to create a new instance.

!!! Warning
    Since the `get_or_create()` is doing a [get](#get) internally, it can also raise a
    [MultipleObjectsReturned](../exceptions.md#multipleobjectsreturned).

You can pass positional ModelRefs to this method.

### Update or create

When you need to update an existing model instance from the matching query. If exists, returns or creates
a new one in case of not existing.

Returns a tuple of `instance` and boolean `created`.

```python
user, created = await User.query.update_or_create(email="foo@bar.com", defaults={
    "is_active": False, "first_name": "Foo"
})
```

This will query the `User` model with the `email` as the lookup key. If it doesn't exist, then it
will use that value with the `defaults` provided to create a new instance.

!!! Warning
    Since the `get_or_create()` is doing a [get](#get) internally, it can also raise a
    [MultipleObjectsReturned](../exceptions.md#multipleobjectsreturned).

You can pass positional ModelRefs to this method.

### Bulk create

When you need to create many instances in one go, or `in bulk`.

```python
await User.query.bulk_create([
    {"email": "foo@bar.com", "first_name": "Foo", "last_name": "Bar", "is_active": True},
    {"email": "bar@foo.com", "first_name": "Bar", "last_name": "Foo", "is_active": True},
])
```

### Bulk update

When you need to update many instances in one go, or `in bulk`.

```python
await User.query.bulk_create([
    {"email": "foo@bar.com", "first_name": "Foo", "last_name": "Bar", "is_active": True},
    {"email": "bar@foo.com", "first_name": "Bar", "last_name": "Foo", "is_active": True},
])

users = await User.query.all()

for user in users:
    user.is_active = False

await User.query.bulk_update(users, fields=['is_active'])
```

## Operators

There are sometimes the need of adding some extra conditions like `AND`, or `OR` or even the `NOT`
into your queries and therefore Edgy provides a simple integration with those.

Edgy provides the [and_](#and), [or_](#or) and [not_](#not) operators directly for you to use, although
this ones come with a slighly different approach.

For all the examples, let us use the model below.

```python
{!> ../docs_src/queries/clauses/model.py !}
```

### SQLAlchemy style

Since Edgy is built on the top of SQL Alchemy core, that also means we can also use directly that
same functionality within our queries.

In other words, uses the [SQLAlchemy style](#sqlalchemy-style).

!!! Warning
    The `or_`, `and_` and `not_` do not work with [related](./related-name.md) operations and only
    directly with the model itself.

This might sound confusing so let us see some examples.

#### AND

As the name suggests, you want to add the `AND` explicitly.

```python
{!> ../docs_src/queries/clauses/and.py !}
```

As mentioned before, applying the [SQLAlchemy style](#sqlalchemy-style) also means you can do this.

```python
{!> ../docs_src/queries/clauses/and_two.py !}
```

And you can do nested `querysets` like multiple [filters](#filter).

```python
{!> ../docs_src/queries/clauses/and_m_filter.py !}
```

#### OR

The same principle as the [and_](#and) but applied to the `OR`.

```python
{!> ../docs_src/queries/clauses/or.py !}
```

As mentioned before, applying the [SQLAlchemy style](#sqlalchemy-style) also means you can do this.

```python
{!> ../docs_src/queries/clauses/or_two.py !}
```

And you can do nested `querysets` like multiple [filters](#filter).

```python
{!> ../docs_src/queries/clauses/or_m_filter.py !}
```

#### NOT

This is simple and direct, this is where you apply the `NOT`.

```python
{!> ../docs_src/queries/clauses/not.py !}
```

As mentioned before, applying the [SQLAlchemy style](#sqlalchemy-style) also means you can do this.

```python
{!> ../docs_src/queries/clauses/not_two.py !}
```

And you can do nested `querysets` like multiple [filters](#filter).

```python
{!> ../docs_src/queries/clauses/not_m_filter.py !}
```

### Edgy Style

This is the most common used scenario where you can use the [related](./related-name.md) for your
queries and all the great functionalities of Edgy while using the operands.

!!! Tip
    The same way you apply the filters for the queries using the [related](./related-name.md), this
    can also be done with the **Edgy style** but the same cannot be said for the
    [SQLAlchemy style](#sqlalchemy-style). So if you want to leverage the full power of Edgy,
    it is advised to go Edgy style.

#### AND

The `AND` operand with the syntax is the same as using the [filter](#filter) or any queryset
operatator but for visualisation purposes this is also available in the format of `and_`.

```python
{!> ../docs_src/queries/clauses/style/and_two.py !}
```

With multiple parameters.

```python
{!> ../docs_src/queries/clauses/style/and.py !}
```

And you can do nested `querysets` like multiple [filters](#filter).

```python
{!> ../docs_src/queries/clauses/style/and_m_filter.py !}
```

#### OR

The same principle as the [and_](#and) but applied to the `OR`.

```python
{!> ../docs_src/queries/clauses/style/or.py !}
```

With multiple `or_` or multiple parametes in the same `or_`

```python
{!> ../docs_src/queries/clauses/style/or_two.py !}
```

And you can do nested `querysets` like multiple [filters](#filter).

```python
{!> ../docs_src/queries/clauses/style/or_m_filter.py !}
```

#### NOT

The `not_` as the same principle as the [exclude](#exclude) and like the [and](#and), for
representation purposes, Edgy also has that function.

```python
{!> ../docs_src/queries/clauses/style/not.py !}
```

With multiple `not_`.

```python
{!> ../docs_src/queries/clauses/style/not_two.py !}
```

And you can do nested `querysets` like multiple [filters](#filter).

```python
{!> ../docs_src/queries/clauses/style/not_m_filter.py !}
```

Internally, the `not_` is calling the [exclude](#exclude) and applying the operators so this is
more for *cosmetic* purposes than anything else, really.

## Blocking Queries

What happens if you want to use Edgy with a blocking operation? So by blocking means `sync`.
For instance, Flask does not support natively `async` and Edgy is an async agnotic ORM and you
probably would like to take advantage of Edgy but you want without doing a lot of magic behind.

Well, Edgy also supports the `run_sync` functionality that allows you to run the queries in
*blocking* mode with ease!

### How to use

You simply need to use the `run_sync` functionality from Edgy and make it happen almost immediately.

```python
from edgy import run_sync
```

All the available functionalities of Edgy run within this wrapper without extra syntax.

Let us see some examples.

**Async mode**

```python
await User.query.all()
await User.query.filter(name__icontains="example")
await User.query.create(name="Edgy")
```

**With run_sync**

```python
from edgy import run_sync

run_sync(User.query.all())
run_sync(User.query.filter(name__icontains="example"))
run_sync(User.query.create(name="Edgy"))
```

And that is it! You can now run all queries synchronously within any framework, literally.

## Cross database queries

Suppose you have a chain of db1 -> db2 -> db3. Give you specified foreign keys queries across them is as easy as:

`fk_to_db2__fk_to_db3=value`

There is a performance penalty doing so because we have to load the whole matching values of db3 to calculate the values of db2 and then to use the values to filter the original query but this works.

Under the hood dynamic queries are used.

## Dynamic queries

Instead of providing a value to filter, it is also possible to provide a sync/async function which takes
as positional argument the current queryset.

The returned value is now used.

This works for edgy style as well as SQLALchemy style queries.

Note: sqlalchemy provides a similar functionality which does not take an argument. Also it is sync only.
It is called lambda statement.


## Raw database queries

Sometimes it is necessary to skip all edgy query modifications and issue raw queries.
We can simply use the `database` and `table` attribute of a Model or QuerySet like we can do in databasez.
For getting the right objects QuerySet has the async function `build_where_clause` which evaluates all dynamic queries and returns an expression.
The pendant in a model are `identifying_clauses`.

``` python
# note: we don't await
query = Model.query.filter(id=1)
# ensures that the db connection doesn't drop during operation
async with query.database as database:
    # when using joins a subquery is generated
    expression = query.table.select().where(await query.build_where_clause())
    # as generic sql
    print(str(expression))
    # as dialect specific sql
    print(expression.compile(database.engine))
    # use with sqlalchemy/databasez
    await database.fetch_all()
```

or direct with a model:

``` python
# ensures that the db connection doesn't drop during operation
async with model.database as database:
    expression = model.table.select().where(*model.identifying_clauses)
    # as generic sql
    print(str(expression))
    # as dialect specific sql
    print(expression.compile(database.engine))
    # use with sqlalchemy/databasez
    await database.fetch_all(expression)
```

If you want raw sql see the print statements. You most probably want a dialect specific sql string for non-basic
sql types because otherwise some features are not supported or cause warnings.

## Debugging

QuerySet contains a cached debug property named `sql` which contains the QuerySet as query with inserted blanks.

[model]: ../models.md
[managers]: ../managers.md
[lambda statements](https://docs.sqlalchemy.org/en/20/core/sqlelement.html#sqlalchemy.sql.expression.lambda_stmt)
