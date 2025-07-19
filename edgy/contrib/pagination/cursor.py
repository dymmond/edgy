from __future__ import annotations

from collections.abc import AsyncGenerator, Hashable, Iterable
from typing import TYPE_CHECKING, Any

from .base import BasePage, BasePaginator

if TYPE_CHECKING:
    from edgy.core.db.models.types import BaseModelType
    from edgy.core.db.querysets import QuerySet


class CursorPage(BasePage):
    """
    Represents a single page in a cursor-based pagination scheme.

    Attributes:
        next_cursor (Hashable | None): The cursor for the next page.
        current_cursor (Hashable | None): The cursor that was used to fetch the current page.
    """

    next_cursor: Hashable | None
    current_cursor: Hashable | None


class CursorPaginator(BasePaginator[CursorPage]):
    """
    A paginator that implements cursor-based pagination.

    This paginator allows for efficient navigation through large datasets by using a cursor
    (typically a unique identifier or a combination of ordered attributes) to determine
    the starting point for the next or previous page.

    Args:
        queryset (QuerySet): The queryset to paginate.
        page_size (int): The maximum number of items per page.
        next_item_attr (str): The attribute used to determine the 'next' item in the pagination.
                              Defaults to an empty string.
        previous_item_attr (str): The attribute used to determine the 'previous' item in the pagination.
                                  Defaults to an empty string.
    """

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
        """
        Calculates the search vector used for filtering based on the `order_by` criteria.

        The search vector consists of field names with `__gte` or `__lt`/`__lte` suffixes
        depending on the ordering (ascending/descending) to build the WHERE clause for
        cursor-based pagination.

        Returns:
            tuple[str, ...]: A tuple of strings representing the search vector.
        """
        vector = [
            f"{criteria[1:]}__lte" if criteria.startswith("-") else f"{criteria}__gte"
            for criteria in self.order_by[:-1]
        ]
        criteria = self.order_by[-1]
        vector.append(f"{criteria[1:]}__lt" if criteria.startswith("-") else f"{criteria}__gt")

        return tuple(vector)

    def cursor_to_vector(self, cursor: Hashable) -> tuple[Hashable, ...]:
        """
        Converts a single cursor or a tuple of cursors into a vector.

        If the cursor is already a tuple, it is returned as is. If it's a single value,
        it's converted into a single-element tuple. This is necessary when `order_by`
        has multiple fields.

        Args:
            cursor (Hashable): The cursor to convert.

        Returns:
            tuple[Hashable, ...]: The cursor represented as a tuple (vector).

        Raises:
            AssertionError: If `order_by` has more than one element and a non-tuple cursor is provided.
        """
        if isinstance(cursor, tuple):
            return cursor
        assert len(self.order_by) == 1
        return (cursor,)

    def vector_to_cursor(self, vector: tuple[Hashable, ...]) -> Hashable:
        """
        Converts a cursor vector back into a single cursor or a tuple of cursors.

        If the `order_by` criteria involves multiple fields, the vector is returned
        as a tuple. Otherwise, the first (and only) element of the vector is returned.

        Args:
            vector (tuple[Hashable, ...]): The cursor vector to convert.

        Returns:
            Hashable: The cursor.
        """
        if len(self.order_by) > 1:
            return vector
        return vector[0]

    def obj_to_vector(self, obj: Any) -> tuple:
        """
        Converts a model instance into a cursor vector.

        This is done by extracting the values of the fields specified in `order_by`
        from the given object.

        Args:
            obj (Any): The model instance to convert.

        Returns:
            tuple: A tuple representing the cursor vector for the object.
        """
        return tuple(getattr(obj, attr.lstrip("-")) for attr in self.order_by)

    def obj_to_cursor(self, obj: Any) -> Hashable:
        """
        Converts a model instance into a cursor.

        This method first converts the object to a vector using `obj_to_vector` and
        then converts that vector into a cursor using `vector_to_cursor`.

        Args:
            obj (Any): The model instance to convert.

        Returns:
            Hashable: The cursor representing the object's position.
        """
        return self.vector_to_cursor(self.obj_to_vector(obj))

    def clear_caches(self) -> None:
        """
        Clears all internal caches used by the paginator, including the reverse page cache.
        """
        super().clear_caches()
        self._reverse_page_cache.clear()

    def convert_to_page(
        self, inp: Iterable, /, cursor: Hashable | None, is_first: bool, reverse: bool = False
    ) -> CursorPage:
        """
        Converts a list of items into a `CursorPage` object.

        This method extends the base `convert_to_page` by adding `next_cursor` and
        `current_cursor` attributes to the resulting page.

        Args:
            inp (Iterable): The input iterable of items to convert into a page.
            cursor (Hashable | None): The cursor used to fetch this page, or None if it's the first page.
            is_first (bool): True if this is considered the first page, False otherwise.
            reverse (bool): True if the pagination is in reverse order, False otherwise.

        Returns:
            CursorPage: The created CursorPage object.
        """
        page_obj: BasePage = super().convert_to_page(
            inp,
            is_first=is_first,
            reverse=reverse,
        )
        next_cursor = self.obj_to_cursor(page_obj.content[-1]) if page_obj.content else None
        return CursorPage(
            content=page_obj.content,
            is_first=page_obj.is_first,
            is_last=page_obj.is_last,
            next_cursor=next_cursor,
            current_cursor=cursor,
        )

    async def get_extra_before(self, cursor: Hashable) -> list[BaseModelType]:
        """
        Retrieves an extra item that comes immediately before the given cursor.

        This is used to determine if the current page is the 'first' page when navigating
        backward or if there are items preceding the current cursor.

        Args:
            cursor (Hashable): The cursor to check for preceding items.

        Returns:
            list[BaseModelType]: A list containing the extra item, or an empty list if none exists.
        """
        vector = self.cursor_to_vector(cursor)
        rpaginator = self.get_reverse_paginator()
        return await rpaginator.queryset.filter(
            **dict(zip(rpaginator.search_vector, vector, strict=False))
        ).limit(1)

    async def exists_extra_before(self, cursor: Hashable) -> bool:
        """
        Checks if there exists an extra item immediately before the given cursor.

        Args:
            cursor (Hashable): The cursor to check for preceding items.

        Returns:
            bool: True if an extra item exists before the cursor, False otherwise.
        """
        vector = self.cursor_to_vector(cursor)
        rpaginator = self.get_reverse_paginator()
        return await rpaginator.queryset.filter(
            **dict(zip(rpaginator.search_vector, vector, strict=False))
        ).exists()

    async def _get_page_after(
        self,
        vector: tuple[Hashable, ...] | None,
        injected_extra: list[BaseModelType] | None = None,
        reverse: bool = False,
    ) -> tuple[CursorPage, list[BaseModelType]]:
        """
        Internal method to fetch a page after a given cursor vector.

        This method handles the core logic for fetching a page and determining if it's the
        first page, potentially injecting extra items if available.

        Args:
            vector (tuple[Hashable, ...] | None): The cursor vector to start fetching from,
                                                 or None for the very first page.
            injected_extra (list[BaseModelType] | None): A list of extra items to prepend
                                                          to the fetched content.
            reverse (bool): True if fetching in reverse order, False otherwise.

        Returns:
            tuple[CursorPage, list[BaseModelType]]: A tuple containing the `CursorPage` object
                                                     and the raw list of items fetched.
        """
        query = self.queryset.limit(self.page_size + 1) if self.page_size else self.queryset
        if vector is not None:
            query = query.filter(**dict(zip(self.search_vector, vector, strict=False)))
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

        page_obj = self.convert_to_page(
            resultarr,
            cursor=None if vector is None else self.vector_to_cursor(vector),
            is_first=is_first,
            reverse=reverse,
        )
        return page_obj, resultarr

    async def get_page_after(self, cursor: Hashable | None = None) -> CursorPage:
        """
        Retrieves the page of results immediately following the given cursor.

        If no cursor is provided, it fetches the first page. Results are cached.

        Args:
            cursor (Hashable | None): The cursor to start fetching from, or None for the first page.

        Returns:
            CursorPage: The page of results after the specified cursor.
        """
        vector: tuple[Hashable, ...] | None = None
        if cursor is not None:
            vector = self.cursor_to_vector(cursor)
        if vector in self._page_cache:
            page_obj = self._page_cache[vector]
            return page_obj
        page_obj = (await self._get_page_after(vector=vector))[0]
        self._page_cache[vector] = page_obj
        return page_obj

    async def get_page_before(self, cursor: Hashable | None = None) -> CursorPage:
        """
        Retrieves the page of results immediately preceding the given cursor.

        This method effectively paginates backward. Results are cached.

        Args:
            cursor (Hashable | None): The cursor to start fetching backward from, or None for the "last"
            page in reverse.

        Returns:
            CursorPage: The page of results before the specified cursor.
        """
        vector: tuple[Hashable, ...] | None = None
        if cursor is not None:
            vector = self.cursor_to_vector(cursor)
        if vector in self._reverse_page_cache:
            page_obj = self._reverse_page_cache[vector]
            return page_obj
        reverse_paginator = self.get_reverse_paginator()
        new_vector: tuple[Hashable, ...] | None = None
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
            current_cursor=None if vector is None else self.vector_to_cursor(vector),
        )
        self._reverse_page_cache[vector] = reverse_page
        return page_obj

    async def get_page(self, cursor: Hashable | None = None, backward: bool = False) -> CursorPage:
        """
        Retrieves a page of results, either forward or backward from a given cursor.

        Args:
            cursor (Hashable | None): The cursor to start fetching from. If None,
                                     it fetches the first page (or "last" in reverse).
            backward (bool): If True, fetches the page before the cursor. If False,
                             fetches the page after the cursor.

        Returns:
            CursorPage: The requested page of results.
        """
        # this reverse only reverses the direction in which the cursor is evaluated
        if backward:
            return await self.get_page_before(cursor)
        else:
            return await self.get_page_after(cursor)

    async def paginate(
        self, start_cursor: Hashable | None = None, stop_cursor: Hashable | None = None
    ) -> AsyncGenerator[CursorPage, None]:
        """
        Paginates through the queryset using cursors, yielding `CursorPage` objects.

        This asynchronous generator allows for iterating over pages of results.
        It can start from a `start_cursor` and stop before a `stop_cursor`.

        Args:
            start_cursor (Hashable | None): The cursor from which to start pagination.
                                            If None, pagination starts from the beginning.
            stop_cursor (Hashable | None): The cursor at which to stop pagination (exclusive).
                                           If None, pagination continues until the end.

        Yields:
            AsyncGenerator[CursorPage, None]: An asynchronous generator that yields `CursorPage` objects.
        """
        query = self.queryset
        prefill_container = []
        start_vector: tuple[Hashable, ...] | None = None
        if start_cursor is not None:
            start_vector = self.cursor_to_vector(start_cursor)
            query = query.filter(**dict(zip(self.search_vector, start_vector, strict=False)))
            if self.previous_item_attr:
                prefill_container = await self.get_extra_before(start_vector)
        if stop_cursor is not None:
            stop_vector = self.cursor_to_vector(stop_cursor)
            query = query.filter(
                **dict(zip(self.get_reverse_paginator().search_vector, stop_vector, strict=False))
            )
        current_cursor: Hashable | None = (
            None if start_vector is None else self.vector_to_cursor(start_vector)
        )
        async for page in self.paginate_queryset(
            query,
            is_first=bool(start_cursor is None and not prefill_container),
            prefill=prefill_container,
        ):
            next_cursor = self.obj_to_cursor(page.content[-1]) if page.content else None
            yield CursorPage(
                **page.__dict__, next_cursor=next_cursor, current_cursor=current_cursor
            )
            current_cursor = next_cursor
