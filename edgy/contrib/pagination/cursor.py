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
    reverse_paginator: CursorPaginator | None = None

    def __init__(
        self,
        queryset: QuerySet,
        page_size: int,
        cursor_def: str,
        next_item_attr: str = "",
        previous_item_attr: str = "",
    ) -> None:
        super().__init__(
            queryset=queryset,
            page_size=page_size,
            order_by=(cursor_def,),
            next_item_attr=next_item_attr,
            previous_item_attr=previous_item_attr,
        )
        self.cursor_field = self.order_by[0]
        if self.cursor_field.startswith("-"):
            self.cursor_field = self.cursor_field[1:]
        field = self.queryset.model_class.meta.fields[self.cursor_field]
        assert not field.null, "cursor_field cannot be nullable."

    def convert_to_page(self, inp: Iterable, /, is_first: bool) -> CursorPage:
        page_obj: Page = super().convert_to_page(inp, is_first=is_first)
        next_cursor = (
            getattr(page_obj.content[-1], self.cursor_field) if page_obj.content else None
        )
        return CursorPage(content=page_obj.content, is_first=page_obj.is_first, is_last=page_obj.is_last, next_cursor=next_cursor)

    async def get_extra(self, cursor: Hashable) -> list:
        query = self.get_reverse_paginator().queryset
        # inverted
        if self.order_by[0].startswith("-"):
            query = query.filter(**{f"{self.cursor_field}__gt": cursor})
        else:
            query = query.filter(**{f"{self.cursor_field}__lt": cursor})
        query = query.limit(1)
        return await query

    async def get_page_after(self, cursor: Hashable = None) -> CursorPage:
        if cursor in self._page_cache:
            page_obj = self._page_cache[cursor]
            return page_obj
        query = self.queryset.limit(self.page_size + 1)
        if cursor is not None:
            if self.order_by[0].startswith("-"):
                query = query.filter(**{f"{self.cursor_field}__lt": cursor})
            else:
                query = query.filter(**{f"{self.cursor_field}__gt": cursor})
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
        reverse_page = await self.get_reverse_paginator().get_page_after(cursor)
        return CursorPage(content=reverse_page.content[::-1], is_first=reverse_page.is_last, is_last=reverse_page.is_first, next_cursor=reverse_page.next_cursor)

    async def get_page(
        self, cursor: Hashable = None, reverse: bool = False
    ) -> CursorPage:
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
                query = query.filter(**{f"{self.cursor_field}__lt": start_cursor})
            else:
                query = query.filter(**{f"{self.cursor_field}__gt": start_cursor})
            if self.previous_item_attr:
                prefill_container = await self.get_extra(start_cursor)
        if stop_cursor is not None:
            if self.order_by[0].startswith("-"):
                query = query.filter(**{f"{self.cursor_field}__gt": stop_cursor})
            else:
                query = query.filter(**{f"{self.cursor_field}__lt": stop_cursor})
        async for page in self.paginate_queryset(
            query,
            is_first=bool(start_cursor is None and not prefill_container),
            prefill=prefill_container,
        ):
            yield page

    def get_reverse_paginator(self) -> CursorPaginator:
        if self.reverse_paginator is None:
            self.reverse_paginator = reverse_paginator = type(self)(
                self.queryset,
                page_size=self.page_size,
                cursor_def=self.cursor_field
                if self.order_by[0].startswith("-")
                else f"-{self.cursor_field}",
                next_item_attr=self.next_item_attr,
                previous_item_attr=self.previous_item_attr,
            )
            reverse_paginator.reverse_paginator = self
        return self.reverse_paginator
