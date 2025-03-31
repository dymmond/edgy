from __future__ import annotations

from collections.abc import AsyncGenerator, Hashable, Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

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
        super().__init__(
            queryset=queryset,
            page_size=page_size,
            next_item_attr=next_item_attr,
            previous_item_attr=previous_item_attr,
        )
        self._reverse_page_cache: dict[Hashable, CursorPage] = {}
        self.search_vector = self.calculate_search_vector()

    def calculate_search_vector(self) -> tuple[str, ...]:
        vector = [
            f"{criteria[1:]}__lte" if criteria.startswith("-") else f"{criteria}__gte"
            for criteria in self.order_by[:-1]
        ]
        criteria = self.order_by[-1]
        vector.append(f"{criteria[1:]}__lt" if criteria.startswith("-") else f"{criteria}__gt")

        return tuple(vector)

    def cursor_to_vector(self, cursor: Hashable) -> tuple[Hashable, ...]:
        if isinstance(cursor, tuple):
            return cursor
        assert len(self.order_by) == 1
        return (cursor,)

    def vector_to_cursor(self, vector: tuple[Hashable, ...]) -> Hashable:
        if len(self.order_by) > 1:
            return vector
        return vector[0]

    def obj_to_cursor(self, obj: Any) -> Hashable:
        return self.vector_to_cursor(
            tuple(getattr(obj, attr.lstrip("-")) for attr in self.order_by)
        )

    def clear_caches(self) -> None:
        super().clear_caches()
        self._reverse_page_cache.clear()

    def convert_to_page(self, inp: Iterable, /, is_first: bool) -> CursorPage:
        page_obj: Page = super().convert_to_page(inp, is_first=is_first)
        next_cursor = self.obj_to_cursor(page_obj.content[-1]) if page_obj.content else None
        return CursorPage(
            content=page_obj.content,
            is_first=page_obj.is_first,
            is_last=page_obj.is_last,
            next_cursor=next_cursor,
        )

    async def get_extra_before(self, cursor: Hashable) -> list:
        vector = self.cursor_to_vector(cursor)
        rpaginator = self.get_reverse_paginator()
        return await rpaginator.queryset.filter(
            **dict(zip(rpaginator.search_vector, vector))
        ).limit(1)

    async def exists_extra_before(self, cursor: Hashable) -> bool:
        vector = self.cursor_to_vector(cursor)
        rpaginator = self.get_reverse_paginator()
        return await rpaginator.queryset.filter(
            **dict(zip(rpaginator.search_vector, vector))
        ).exists()

    async def get_page_after(self, cursor: Hashable = None) -> CursorPage:
        if cursor is not None:
            cursor = self.cursor_to_vector(cursor)
        if cursor in self._page_cache:
            page_obj = self._page_cache[cursor]
            return page_obj
        query = self.queryset.limit(self.page_size + 1) if self.page_size else self.queryset
        if cursor is not None:
            query = query.filter(**dict(zip(self.search_vector, cursor)))
        is_first = cursor is None
        if not is_first and self.previous_item_attr:
            resultarr = await self.get_extra_before(cursor)
            # if on first position
            if not resultarr:
                is_first = True
            resultarr.extend(await query)
        elif not is_first and not await self.exists_extra_before(cursor):
            is_first = True
        else:
            resultarr = await query

        page_obj = self.convert_to_page(resultarr, is_first=is_first)
        self._page_cache[cursor] = page_obj
        return page_obj

    async def get_page_before(self, cursor: Hashable = None) -> CursorPage:
        if cursor is not None:
            cursor = self.cursor_to_vector(cursor)
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
            start_vector = self.cursor_to_vector(start_cursor)
            query = query.filter(**dict(zip(self.search_vector, start_vector)))
            if self.previous_item_attr:
                prefill_container = await self.get_extra_before(start_vector)
        if stop_cursor is not None:
            stop_vector = self.cursor_to_vector(stop_cursor)
            query = query.filter(
                **dict(zip(self.get_reverse_paginator().search_vector, stop_vector))
            )
        async for page in self.paginate_queryset(
            query,
            is_first=bool(start_cursor is None and not prefill_container),
            prefill=prefill_container,
        ):
            yield page
