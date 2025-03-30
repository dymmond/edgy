from __future__ import annotations

from collections.abc import AsyncGenerator, Hashable, Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .base import Page, Paginator

if TYPE_CHECKING:
    from edgy.core.db.querysets import QuerySet


@dataclass
class CursorPage(Page):
    next_cursor: Hashable = None


class CursorPaginator(Paginator[CursorPage]):
    def __init__(
        self,
        queryset: QuerySet,
        page_size: int,
        next_item_attr: str = "",
        previous_item_attr: str = "",
    ) -> None:
        if len(queryset._order_by) != 1:
            raise ValueError("You must pass a QuerySet with .order_by(cursor_column)")
        super().__init__(
            queryset=queryset,
            page_size=page_size,
            next_item_attr=next_item_attr,
            previous_item_attr=previous_item_attr,
        )
        self._reverse_page_cache: dict[Hashable, CursorPage] = {}
        self.cursor_column = self.order_by[0]
        if self.cursor_column.startswith("-"):
            self.cursor_column = self.cursor_column[1:]
        column = self.queryset.model_class.table.columns.get(self.cursor_column)
        if column is None:
            raise ValueError("cursor_column does not exist.")
        if column.nullable:
            raise ValueError("cursor_column cannot be nullable.")

    def clear_caches(self) -> None:
        super().clear_caches()
        self._reverse_page_cache.clear()

    def convert_to_page(self, inp: Iterable, /, is_first: bool) -> CursorPage:
        page_obj: Page = super().convert_to_page(inp, is_first=is_first)
        next_cursor = (
            getattr(page_obj.content[-1], self.cursor_column) if page_obj.content else None
        )
        return CursorPage(
            content=page_obj.content,
            is_first=page_obj.is_first,
            is_last=page_obj.is_last,
            next_cursor=next_cursor,
        )

    async def get_extra(self, cursor: Hashable) -> list:
        query = self.get_reverse_paginator().queryset
        # inverted
        if self.order_by[0].startswith("-"):
            query = query.filter(**{f"{self.cursor_column}__gt": cursor})
        else:
            query = query.filter(**{f"{self.cursor_column}__lt": cursor})
        query = query.limit(1)
        return await query

    async def get_page_after(self, cursor: Hashable = None) -> CursorPage:
        if cursor in self._page_cache:
            page_obj = self._page_cache[cursor]
            return page_obj
        query = self.queryset.limit(self.page_size + 1) if self.page_size else self.queryset
        if cursor is not None:
            if self.order_by[0].startswith("-"):
                query = query.filter(**{f"{self.cursor_column}__lt": cursor})
            else:
                query = query.filter(**{f"{self.cursor_column}__gt": cursor})
        is_first = cursor is None
        if cursor is not None and self.previous_item_attr:
            resultarr = await self.get_extra(cursor)
            # if on first position
            if not resultarr:
                is_first = True
            resultarr.extend(await query)
        else:
            resultarr = await query

        page_obj = self.convert_to_page(resultarr, is_first=is_first)
        self._page_cache[cursor] = page_obj
        return page_obj

    async def get_page_before(self, cursor: Hashable = None) -> CursorPage:
        if cursor in self._reverse_page_cache:
            page_obj = self._reverse_page_cache[cursor]
            return page_obj
        reverse_page = await self.get_reverse_paginator().get_page_after(cursor)
        page_obj = CursorPage(
            content=reverse_page.content[::-1],
            is_first=reverse_page.is_last,
            is_last=reverse_page.is_first,
            next_cursor=reverse_page.next_cursor,
        )
        self._reverse_page_cache[cursor] = page_obj
        return page_obj

    async def get_page(self, cursor: Hashable = None, reverse: bool = False) -> CursorPage:
        if reverse:
            return await self.get_page_before(cursor)
        else:
            return await self.get_page_after(cursor)

    async def paginate(
        self, start_cursor: Hashable = None, stop_cursor: Hashable = None
    ) -> AsyncGenerator[CursorPage, None]:
        query = self.queryset
        prefill_container = []
        if start_cursor is not None:
            if self.order_by[0].startswith("-"):
                query = query.filter(**{f"{self.cursor_column}__lt": start_cursor})
            else:
                query = query.filter(**{f"{self.cursor_column}__gt": start_cursor})
            if self.previous_item_attr:
                prefill_container = await self.get_extra(start_cursor)
        if stop_cursor is not None:
            if self.order_by[0].startswith("-"):
                query = query.filter(**{f"{self.cursor_column}__gt": stop_cursor})
            else:
                query = query.filter(**{f"{self.cursor_column}__lt": stop_cursor})
        async for page in self.paginate_queryset(
            query,
            is_first=bool(start_cursor is None and not prefill_container),
            prefill=prefill_container,
        ):
            yield page
