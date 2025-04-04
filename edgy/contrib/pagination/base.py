from __future__ import annotations

import sys
from collections.abc import AsyncGenerator, Hashable, Iterable
from typing import TYPE_CHECKING, Any, Generic, TypeVar, cast

from pydantic import BaseModel

if TYPE_CHECKING:
    from edgy.core.db.querysets import QuerySet

if sys.version_info >= (3, 11):  # pragma: no cover
    from typing import Self
else:  # pragma: no cover
    from typing_extensions import Self


class Page(BaseModel):
    content: list[Any]
    is_first: bool
    is_last: bool


PageType = TypeVar("PageType", bound=Page)


class Paginator(Generic[PageType]):
    order_by: tuple[str, ...]

    def __init__(
        self,
        queryset: QuerySet,
        page_size: int,
        next_item_attr: str = "",
        previous_item_attr: str = "",
    ) -> None:
        self._reverse_paginator: Self | None = None
        self.page_size = int(page_size)
        if page_size < 0:
            raise ValueError("page_size must be at least 0")
        if len(queryset._order_by) == 0:
            raise ValueError("You must pass a QuerySet with .order_by(*criteria)")
        self.next_item_attr = next_item_attr
        self.previous_item_attr = previous_item_attr
        self.queryset = queryset
        if self.previous_item_attr or self.next_item_attr:
            # copy for not leaking attributes in the cache
            old_queryset = self.queryset
            self.queryset = self.queryset.all()
            # but keep some caches
            self.queryset._cache_count = old_queryset._cache_count
            self.queryset._cached_select_related_expression = (
                old_queryset._cached_select_related_expression
            )
            self.queryset._cached_select_with_tables = old_queryset._cached_select_with_tables
        self.order_by = queryset._order_by
        self._page_cache: dict[Hashable, PageType] = {}

    def clear_caches(self) -> None:
        self._page_cache.clear()
        self.queryset.all(clear_cache=True)
        if self._reverse_paginator:
            self._reverse_paginator = None

    async def get_amount_pages(self) -> int:
        if not self.page_size:
            return 1
        count, remainder = divmod(await self.get_total(), self.page_size)
        return count + (1 if remainder else 0)

    async def get_total(self) -> int:
        return await self.queryset.count()

    async def _get_page(self, page: int, reverse: bool = False) -> Page:
        # this is a special intern reverse which really reverses a page
        if page < 0 and self.page_size:
            return await self.get_reverse_paginator()._get_page(-page, reverse=True)
        else:
            offset = self.page_size * (page - 1)
        if self.previous_item_attr:
            offset = max(offset - 1, 0)
        if self.queryset._cache_fetch_all:
            resultarr = await self.queryset
            if self.page_size:
                resultarr = resultarr[offset : offset + self.page_size + 1]
            return self.convert_to_page(resultarr, is_first=offset == 0, reverse=reverse)
        query = self.queryset
        query = query.offset(offset)
        if self.page_size:
            query = query.limit(self.page_size + 1)
        return self.convert_to_page(await query, is_first=offset == 0, reverse=reverse)

    async def get_page(self, page: int = 1) -> Page:
        if page == 0 or not isinstance(page, int):
            raise ValueError(f"Invalid page parameter value: {page!r}")
        if self.page_size == 0:
            # for caching, there are no other pages, this does not apply to cursor!
            page = 1
        if page in self._page_cache:
            return cast(Page, self._page_cache[page])
        page_obj = await self._get_page(page=page)

        self._page_cache[page] = cast(PageType, page_obj)
        return page_obj

    def convert_to_page(self, inp: Iterable, /, is_first: bool, reverse: bool = False) -> PageType:
        last_item: Any = None
        result_list = []
        item_counter = 0
        drop_first = not is_first and self.previous_item_attr
        for item in inp:
            if reverse:
                if self.next_item_attr:
                    setattr(item, self.next_item_attr, last_item)
                if last_item is not None and self.previous_item_attr:
                    setattr(last_item, self.previous_item_attr, item)
            else:
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
        is_last = bool(self.page_size == 0 or item_counter < min_size)
        if is_last and (
            (not drop_first and item_counter >= 1) or (drop_first and item_counter >= 2)
        ):
            if reverse and self.previous_item_attr:
                setattr(last_item, self.previous_item_attr, None)
            elif not reverse and self.next_item_attr:
                setattr(last_item, self.next_item_attr, None)
            result_list.append(last_item)
        if reverse:
            result_list.reverse()
            return cast(PageType, Page(content=result_list, is_first=is_last, is_last=is_first))
        else:
            return cast(PageType, Page(content=result_list, is_first=is_first, is_last=is_last))

    async def paginate_queryset(
        self, queryset: QuerySet, is_first: bool = True, prefill: Iterable | None = None
    ) -> AsyncGenerator[PageType, None]:
        container: list = []
        if prefill is not None:
            container.extend(prefill)
        page: PageType | None = None
        min_size = self.page_size + 1
        if self.previous_item_attr and not is_first:
            min_size += 1
        if queryset.database.force_rollback:
            for item in await queryset:
                container.append(item)
                if self.page_size and len(container) >= min_size:
                    page = self.convert_to_page(container, is_first=is_first)
                    yield page
                    if self.previous_item_attr and is_first:
                        min_size += 1
                    is_first = False
                    container = [page.content[-1], item] if self.previous_item_attr else [item]
        else:
            async for item in queryset:
                container.append(item)
                if self.page_size and len(container) >= min_size:
                    page = self.convert_to_page(container, is_first=is_first)
                    yield page
                    if self.previous_item_attr and is_first:
                        min_size += 1
                    is_first = False
                    container = [page.content[-1], item] if self.previous_item_attr else [item]
        if page is None or not page.is_last:
            yield self.convert_to_page(container, is_first=is_first)

    async def paginate(self, start_page: int = 1) -> AsyncGenerator[PageType, None]:
        query = self.queryset
        if start_page > 1:
            offset = self.page_size * (start_page - 1)
            if self.previous_item_attr:
                offset = max(offset - 1, 0)
            if offset > 0:
                query = query.offset(offset)
        async for page in self.paginate_queryset(query, is_first=start_page == 1):
            yield page

    def get_reverse_paginator(self) -> Self:
        if self._reverse_paginator is None:
            self._reverse_paginator = type(self)(
                self.queryset.reverse(),
                page_size=self.page_size,
                next_item_attr=self.next_item_attr,
                previous_item_attr=self.previous_item_attr,
            )
            self._reverse_paginator._reverse_paginator = self
        return self._reverse_paginator
