# Pagination

Edgy supports out of the box counter-based as well as cursor based high-performance pagination with optional support
of setting extra attributes so all items are like a double-linked list.

High-performance means, everything is cached smartly and if you re-use the paginator you will may
even skip database access.

It is however not as flexible as the Paginator of django. You can only pass QuerySets.

## Counter-based


## Cursor-based


## Single-page mode (linked lists)

The paginators understand a special value of page_size of 0. Here everything is put on one page.
This way we can transform a QuerySet into a linked list, where every item knows its partners.

`CursorPaginator` is here a bit special: There is only one page but we can still pass a cursor to limitate.

## Reversing

Every paginator has a get_reverse_paginator() method which inverts the query.

## Cache management

Sometimes you need to clear the cache to get fresh results. For this the paginator provides the
`clear_caches` method.
