from __future__ import annotations

from collections.abc import AsyncGenerator, Hashable
from typing import TYPE_CHECKING

from .base import Page, Paginator

if TYPE_CHECKING:
    from edgy.core.db.querysets import QuerySet


class CursorPaginator(Paginator):
    reverse_paginator: CursorPaginator | None = None

    def __init__(self, queryset: QuerySet, page_size: int, cursor_def: str) -> None:
        super().__init__(queryset=queryset, page_size=page_size, order_by=(cursor_def,))
        self.cursor_field = self.order_by[0]
        if self.cursor_field.startswith("-"):
            self.cursor_field = self.cursor_field[1:]
        field = self.queryset.model_class.meta.fields[self.cursor_field]
        assert not field.null, "cursor_field cannot be nullable."

    async def get_page_after(self, cursor: Hashable = None) -> tuple[Page, Hashable]:
        if cursor in self._page_cache:
            query = self._page_cache[cursor]
        elif cursor is None:
            query = self.queryset.limit(self.page_size + 1)
            self._page_cache[cursor] = query
        else:
            if self.order_by[0].startswith("-"):
                query = self.queryset.filter(**{f"{self.cursor_field}__lt": cursor})
            else:
                query = self.queryset.filter(**{f"{self.cursor_field}__gt": cursor})
            query = query.limit(self.page_size)
            self._page_cache[cursor] = query
        resultarr = await query
        if resultarr:
            return Page(
                resultarr[: self.page_size], cursor is None, len(resultarr) <= self.page_size
            ), getattr(resultarr[-1], self.cursor_field)
        return Page(
            resultarr[: self.page_size], cursor is None, len(resultarr) <= self.page_size
        ), None

    async def get_page_before(self, cursor: Hashable = None) -> tuple[Page, Hashable]:
        return await self.get_reverse_paginator().get_page_after(cursor)

    async def get_page(
        self, cursor: Hashable = None, reverse: bool = False
    ) -> tuple[Page, Hashable]:
        if reverse:
            return await self.get_page_before(cursor)
        else:
            return await self.get_page_after(cursor)

    async def paginate(
        self, start_cursor: Hashable = None, stop_cursor: Hashable = None
    ) -> AsyncGenerator[Page, None]:
        container: list = []
        query = self.queryset
        if start_cursor is not None:
            if self.order_by[0].startswith("-"):
                query = query.filter(**{f"{self.cursor_field}__lt": start_cursor})
            else:
                query = query.filter(**{f"{self.cursor_field}__gt": start_cursor})
        if stop_cursor is not None:
            if self.order_by[0].startswith("-"):
                query = query.filter(**{f"{self.cursor_field}__gt": stop_cursor})
            else:
                query = query.filter(**{f"{self.cursor_field}__lt": stop_cursor})
        first: bool = True
        async for item in query:
            if len(container) > self.page_size:
                yield Page(container[:-1], first, False)
                first = False
                container = [container[-1]]
            container.append(item)
        if len(container) > self.page_size:
            yield Page(container[:-1], first, False)
            yield Page(container[-1], False, True)
        else:
            yield Page(container[:-1], first, True)

    def get_reverse_paginator(self) -> CursorPaginator:
        if self.reverse_paginator is None:
            self.reverse_paginator = type(self)(
                self.queryset.reverse(),
                page_size=self.page_size,
                cursor_def=self.cursor_field
                if self.order_by[0].startswith("-")
                else f"-{self.cursor_field}",
            )
        return self.reverse_paginator
