from __future__ import annotations

from collections.abc import AsyncGenerator, Hashable, Iterable
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
        next_item_attr: str = "",
        previous_item_attr: str = "",
    ) -> None:
        self.page_size = int(page_size)
        if page_size < 1:
            raise ValueError("page_size must be at least 1")
        self.next_item_attr = next_item_attr
        self.previous_item_attr = previous_item_attr
        if order_by:
            self.queryset = queryset.order_by(*order_by)
            self.order_by = order_by
        else:
            self.queryset = queryset
            self.order_by = queryset._order_by
        self._page_cache: dict[Hashable, Page] = {}

    async def get_page(self, page: int = 1) -> Page:
        reverse = False
        if page == 0 or not isinstance(page, int):
            raise ValueError(f"Invalid page parameter value: {page!r}")
        if page in self._page_cache:
            return self._page_cache[page]

        if page < 0:
            reverse = True
            offset = self.page_size * (1 - page)
        else:
            offset = self.page_size * (page - 1)
        if self.previous_item_attr:
            offset = max(offset - 1, 0)
        if self.queryset._cache_fetch_all:
            if reverse:
                resultarr = (await self.queryset)[-offset - 1 : -offset - self.page_size - 2 : -1]
            else:
                resultarr = (await self.queryset)[offset : offset + self.page_size + 1]
            page_obj = self.convert_to_page(resultarr, is_first=offset == 0)
            self._page_cache[page] = page_obj
            return page_obj
        query = self.queryset.offset(offset).limit(self.page_size + 1)
        if reverse:
            query = query.reverse()
        page_obj = self.convert_to_page(await query, is_first=offset == 0)
        self._page_cache[page] = page_obj
        return page_obj

    def convert_to_page(self, inp: Iterable, /, is_first: bool) -> Page:
        last_item: Any = None
        result_list = []
        item_counter = 0
        drop_first = not is_first and self.previous_item_attr
        for item in inp:
            if self.previous_item_attr:
                setattr(item, self.previous_item_attr, last_item)
            if last_item is not None and self.next_item_attr:
                setattr(last_item, self.next_item_attr, item)
            if (not drop_first and item_counter >= 1) or (drop_first and item_counter >= 2):
                result_list.append(last_item)
            last_item = item
            item_counter += 1
        min_size = self.page_size + 1
        if self.previous_item_attr and not is_first:
            min_size += 1
        is_last = item_counter < min_size
        if is_last and (
            (not drop_first and item_counter >= 1) or (drop_first and item_counter >= 2)
        ):
            if self.next_item_attr:
                setattr(last_item, self.next_item_attr, None)
            result_list.append(last_item)
        return Page(content=result_list, is_first=is_first, is_last=is_last)

    async def paginate_queryset(
        self, queryset: QuerySet, is_first: bool = True, prefill: Iterable | None = None
    ) -> AsyncGenerator[Page, None]:
        container: list = []
        if prefill is not None:
            container.extend(prefill)
        page: Page | None = None
        min_size = self.page_size + 1
        if self.previous_item_attr and not is_first:
            min_size += 1
        if queryset.database.force_rollback:
            for item in await queryset:
                container.append(item)
                if len(container) >= min_size:
                    page = self.convert_to_page(container, is_first=is_first)
                    yield page
                    if self.previous_item_attr and is_first:
                        min_size += 1
                    is_first = False
                    container = [page.content[-1], item] if self.previous_item_attr else [item]
        else:
            async for item in queryset:
                container.append(item)
                if len(container) >= min_size:
                    page = self.convert_to_page(container, is_first=is_first)
                    yield page
                    if self.previous_item_attr and is_first:
                        min_size += 1
                    is_first = False
                    container = [page.content[-1], item] if self.previous_item_attr else [item]
        if page is None or not page.is_last:
            yield self.convert_to_page(container, is_first=is_first)

    async def paginate(self, start_page: int = 1) -> AsyncGenerator[Page, None]:
        query = self.queryset
        if start_page > 1:
            offset = self.page_size * (start_page - 1)
            if self.previous_item_attr:
                offset = max(offset - 1, 0)
            if offset > 0:
                query = query.offset(offset)
        async for page in self.paginate_queryset(query, is_first=start_page == 1):
            yield page

    def get_reverse_paginator(self) -> Paginator:
        if self.reverse_paginator is None:
            self.reverse_paginator = type(self)(
                self.queryset.reverse(),
                page_size=self.page_size,
                next_item_attr=self.next_item_attr,
                previous_item_attr=self.previous_item_attr,
            )
        return self.reverse_paginator
