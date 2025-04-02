from __future__ import annotations

from collections.abc import AsyncGenerator, Hashable, Iterable
from typing import TYPE_CHECKING, Any

from .base import Page, Paginator

if TYPE_CHECKING:
    from edgy.core.db.models.types import BaseModelType
    from edgy.core.db.querysets import QuerySet


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

    def obj_to_vector(self, obj: Any) -> tuple:
        return tuple(getattr(obj, attr.lstrip("-")) for attr in self.order_by)

    def obj_to_cursor(self, obj: Any) -> Hashable:
        return self.vector_to_cursor(self.obj_to_vector(obj))

    def clear_caches(self) -> None:
        super().clear_caches()
        self._reverse_page_cache.clear()

    def convert_to_page(
        self, inp: Iterable, /, is_first: bool, reverse: bool = False
    ) -> CursorPage:
        page_obj: Page = super().convert_to_page(inp, is_first=is_first, reverse=reverse)
        next_cursor = self.obj_to_cursor(page_obj.content[-1]) if page_obj.content else None
        return CursorPage(
            content=page_obj.content,
            is_first=page_obj.is_first,
            is_last=page_obj.is_last,
            next_cursor=next_cursor,
        )

    async def get_extra_before(self, cursor: Hashable) -> list[BaseModelType]:
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

    async def _get_page_after(
        self,
        vector: tuple | None,
        injected_extra: list[BaseModelType] | None = None,
        reverse: bool = False,
    ) -> tuple[CursorPage, list[BaseModelType]]:
        query = self.queryset.limit(self.page_size + 1) if self.page_size else self.queryset
        if vector is not None:
            query = query.filter(**dict(zip(self.search_vector, vector)))
        is_first = vector is None
        if not is_first and self.previous_item_attr:
            resultarr = (
                await self.get_extra_before(vector) if injected_extra is None else injected_extra
            )
            # if on first position
            if not resultarr:
                is_first = True
            resultarr.extend(await query)
        elif injected_extra is not None:
            if injected_extra:
                is_first = False
            injected_extra.extend(await query)
            resultarr = injected_extra
        else:
            if not is_first and not await self.exists_extra_before(vector):
                is_first = True
            resultarr = await query

        page_obj = self.convert_to_page(resultarr, is_first=is_first, reverse=reverse)
        return page_obj, resultarr

    async def get_page_after(self, cursor: Hashable = None) -> CursorPage:
        vector: tuple | None = None
        if cursor is not None:
            vector = self.cursor_to_vector(cursor)
        if vector in self._page_cache:
            page_obj = self._page_cache[vector]
            return page_obj
        page_obj = (await self._get_page_after(vector=vector))[0]
        self._page_cache[vector] = page_obj
        return page_obj

    async def get_page_before(self, cursor: Hashable = None) -> CursorPage:
        vector: tuple | None = None
        if cursor is not None:
            vector = self.cursor_to_vector(cursor)
        if vector in self._reverse_page_cache:
            page_obj = self._reverse_page_cache[vector]
            return page_obj
        reverse_paginator = self.get_reverse_paginator()
        new_vector: tuple | None = None
        # to match the cursors we need to go back one more item
        injected_reverse = (
            await reverse_paginator.get_extra_before(vector) if vector is not None else []
        )
        if injected_reverse:
            new_vector = self.obj_to_vector(injected_reverse[0])
        # instead of recalculating get_extra_before inject the item
        # we need the extra item in the array (is_last) if it exists, so we match the cursor of
        # get_page_after
        reverse_page, raw_array = await reverse_paginator._get_page_after(
            new_vector, injected_extra=injected_reverse, reverse=True
        )
        page_obj = CursorPage(
            content=reverse_page.content,
            is_first=reverse_page.is_first,
            is_last=reverse_page.is_last,
            next_cursor=self.obj_to_cursor(raw_array[-1]) if raw_array else None,
        )
        self._reverse_page_cache[vector] = reverse_page
        return page_obj

    async def get_page(self, cursor: Hashable = None, backward: bool = False) -> CursorPage:
        # this reverse only reverses the direction in which the cursor is evaluated
        if backward:
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
