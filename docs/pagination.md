# Pagination

**edgy** offers built-in support for both counter-based and cursor-based high-performance pagination. You can also set extra attributes to make all items behave like a double-linked list.

**High-performance** means smart caching is used, so if you reuse the paginator, you might even skip database access. This works because it reuses the order of the QuerySet, which may already have the entire query cached.

However, **edgy** is not as flexible as Django's Paginator. It only accepts QuerySets.

## Counter-based

This is the classic way of pagination. You provide a page number, and it returns a specific set of items based on the order of the QuerySet.

```python
{!> ../docs_src/pagination/simple_pagination.py !}
```

You can also use attributes to get the previous or next item. For better performance, we use the CursorPaginator:

```python
{!> ../docs_src/pagination/using_attributes.py !}
```

This example would be in the slow variant:

```python
{!> ../docs_src/pagination/using_attributes_slow.py !}
```

!!! Note
    If you use a StrictModel make sure you have placeholders in place.

## Cursor-based

This pagination works like the counter-based one but supports only one column: It is used as a cursor.
This is more efficient and allows querying for new contents, in case of sequential cursors.

```python
{!> ../docs_src/pagination/cursor_pagination.py !}
```

Because you can have vectors as cursors, you can also use this paginator to calculate efficiently the partners for
a single item like shown above:

```python
{!> ../docs_src/pagination/using_attributes.py !}
```

## NumberedPaginator

If you are more familiar with Django Rest Framework like NumberedPaginator, this does a similar job.

```python
{!> ../docs_src/pagination/number_pagination.py !}
```

## Integration

How would an application look like, using this feature?

Here an example for esmerald with cursors and attributes:

```python
{!> ../docs_src/pagination/esmerald_example.py !}
```

## Special features

### Single-page mode (linked lists)

If you set the `page_size` to 0, all items are displayed on one page. This transforms the QuerySet into a linked list, where each item knows its neighbors.

The `CursorPaginator` works a bit different: it shows only one page, but you can still pass cursors to limit the range.

```python
{!> ../docs_src/pagination/double_linked_list.py !}
```

### Reversing

Every paginator has a `get_reverse_paginator()` method which returns a cached paginator which contains a reversed QuerySet of the current paginator (the order is reversed).

### Cache management

Sometimes you need to clear the cache to get fresh results. For this the paginator provides the
`clear_caches()` method.
