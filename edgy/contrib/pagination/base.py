from __future__ import annotations

from collections.abc import AsyncGenerator, Hashable
from typing import TYPE_CHECKING, Any, NamedTuple

if TYPE_CHECKING:
    from edgy.core.db.querysets import QuerySet


class Page(NamedTuple):
    content: list[Any]
    is_first: bool
    is_last: bool


class Paginator:
    reverse_paginator: Paginator | None = None
    order_by: tuple[str, ...]

    def __init__(
        self,
        queryset: QuerySet,
        page_size: int,
        order_by: tuple[str, ...] | None = None,
    ) -> None:
        self.page_size = page_size
        if order_by:
            self.queryset = queryset.order_by(*order_by)
            self.order_by = order_by
        else:
            self.queryset = queryset
            self.order_by = queryset._order_by
        self._page_cache: dict[Hashable, QuerySet] = {}

    async def get_page(self, page: int = 1) -> Page:
        reverse = False
        if page == 0 or not isinstance(page, int):
            raise ValueError(f"Invalid page parameter value: {page!r}")

        if page < 0:
            reverse = True
            offset = self.page_size * (1 - page)
        else:
            offset = self.page_size * (page - 1)
        if self.queryset._cache_fetch_all:
            if reverse:
                resultarr = (await self.queryset)[-offset - 1 : -offset - self.page_size - 2 : -1]
            resultarr = (await self.queryset)[offset : offset + self.page_size + 1]
            return Page(
                content=resultarr[: self.page_size],
                is_first=offset == 0,
                is_last=len(resultarr) <= self.page_size,
            )
        if page in self._page_cache:
            query = self._page_cache[page]
        else:
            query = self.queryset.offset(offset).limit(self.page_size + 1)
            if reverse:
                query = query.reverse()
            self._page_cache[page] = query
        resultarr = await query
        return Page(
            content=resultarr[: self.page_size],
            is_first=offset == 0,
            is_last=len(resultarr) <= self.page_size,
        )

    async def paginate(self, start_page: int = 1) -> AsyncGenerator[Page, None]:
        container: list = []
        query = self.queryset
        if start_page > 1:
            query = query.offset(self.page_size * (start_page - 1))
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

    def get_reverse_paginator(self) -> Paginator:
        if self.reverse_paginator is None:
            self.reverse_paginator = type(self)(self.queryset.reverse(), page_size=self.page_size)
        return self.reverse_paginator
