# Pagination

Edgy supports out of the box counter-based as well as cursor based high-performance pagination with optional support
of setting extra attributes so all items are like a double-linked list.

High-performance means, everything is cached smartly and if you re-use the paginator you will may
even skip database access.

It is however not as flexible as the Paginator of django. You can only pass QuerySets.

## Counter-based

This is the classic way of pagination. You pass a number and get a page basing on the order of the QuerySet.
You may pass a custom order_by parameter to set an order for the QuerySet.This will however cause a copy.


### Default mode

A note of warning should be said about when not passing an order or the queryset used for hasn't an order:

The Paginator uses the pkcolumns as fallback for ordering. This aligns with the behavior of QuerySet when no order is found.

## Cursor-based


## Single-page mode (linked lists)

The paginators understand a special value of page_size of 0. Here everything is put on one page.
This way we can transform a QuerySet into a linked list, where every item knows its partners.

`CursorPaginator` is here a bit special: There is only one page shown but we can still pass cursors to limitate the range.


## Reversing

Every paginator has a get_reverse_paginator() method which inverts the query. This also reverts the order.
For getting a page before a cursor pass `reverse=True` to get_page.

## Cache management

Sometimes you need to clear the cache to get fresh results. For this the paginator provides the
`clear_caches` method.
