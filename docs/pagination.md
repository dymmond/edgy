# Pagination

Edgy supports out of the box counter-based as well as cursor based high-performance pagination with optional support
of setting extra attributes so all items are like a double-linked list.

High-performance means, everything is cached smartly and if you re-use the paginator you will may
even skip database access. This is why it reuses the order of the QuerySet.
A QuerySet which has already the whole query in cache,

It is however not as flexible as the Paginator of django. You can only pass QuerySets.

## Counter-based

This is the classic way of pagination. You pass a number and get a page basing on the order of the QuerySet.

```python
{!> ../docs_src/pagination/simple_pagination.py !}
```

You may also can use attributes to get the partner before/after. We use the CursorPaginator for more performance.

```python
{!> ../docs_src/pagination/using_attributes.py !}
```
This example would be in the slow variant

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

## Single-page mode (linked lists)

The paginators understand a special value of page_size of 0. Here everything is put on one page.
This way we can transform a QuerySet into a linked list, where every item knows its partners.

`CursorPaginator` is here a bit special: There is only one page shown but we can still pass cursors to limitate the range.


```python
{!> ../docs_src/pagination/double_linked_list.py !}
```

## Reversing

Every paginator has a get_reverse_paginator() method which inverts the query. This also reverts the order.

## Cache management

Sometimes you need to clear the cache to get fresh results. For this the paginator provides the
`clear_caches` method.
