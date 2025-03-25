from __future__ import annotations

from collections.abc import AsyncGenerator, Hashable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from edgy.core.db.querysets import QuerySet
    from edgy.core.db.querysets.types import EdgyEmbedTarget


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

    async def get_page(self, page: int = 1) -> list[EdgyEmbedTarget]:
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
                return (await self.queryset)[-offset - 1 : -offset - self.page_size - 1 : -1]
            return (await self.queryset)[offset : offset + self.page_size]
        if page in self._page_cache:
            query = self._page_cache[page]
        else:
            query = self.queryset.offset(offset).limit(self.page_size)
            if reverse:
                query = query.reverse()
            self._page_cache[page] = query
        return await query

    async def paginate(self, start_page: int = 1) -> AsyncGenerator[tuple[list[EdgyEmbedTarget], bool], None]:
        container: list = []
        query = self.queryset
        if start_page > 1:
            query = query.offset(self.page_size * (start_page - 1))
        async for item in query:
            if len(container) > self.page_size:
                yield container[:-1], True
                container = [container[-1]]
            container.append(item)
        if len(container) > self.page_size:
            yield container[:-1], True
            yield container[-1], False
        else:
            yield container, False

    def get_reverse_paginator(self) -> Paginator:
        if self.reverse_paginator is None:
            self.reverse_paginator = type(self)(self.queryset.reverse(), page_size=self.page_size)
        return self.reverse_paginator
