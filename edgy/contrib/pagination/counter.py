from __future__ import annotations

from collections.abc import AsyncGenerator, Hashable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from edgy.core.db.querysets import QuerySet
    from edgy.core.db.querysets.types import EdgyEmbedTarget



class Paginator:
    def __init__(
        self,
        queryset: QuerySet,
        page_size: int,
        order_by: tuple[str, ...] | None = None,
    ) -> None:
        self.page_size = page_size
        self.order_by = order_by
        self.queryset = queryset.order_by(*self.order_by)
        self._page_cache: dict[Hashable, QuerySet] = {}

    async def get_page(self, page: int = 1) -> list[EdgyEmbedTarget]:
        reverse = False
        if page < 0:
            reverse = True
            base = self.page_size * (-page)
        else:
            base = self.page_size * (page - 1)
        if self.queryset._cache_fetch_all:
            if reverse:
                return (await self.queryset)[-base : -(base + self.page_size) : -1]
            return (await self.queryset)[base : base + self.page_size]
        if page in self._page_cache:
            query = self._page_cache[page]
        else:
            query = self.queryset.offset(base).limit(self.page_size)
            if reverse:
                query = query.reverse()
            self._page_cache[page] = query
        return await query

    async def paginate(self) -> AsyncGenerator[list[EdgyEmbedTarget], None]:
        container: list = []
        async for item in self.queryset:
            if len(container) >= self.page_size:
                yield container
                container = []
            container.append(item)
        yield container
