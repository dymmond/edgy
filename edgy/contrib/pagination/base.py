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


class BasePage(BaseModel):
    """
    Base class for a page of results in a pagination scheme.

    Attributes:
        content (list[Any]): The list of items on the current page.
        is_first (bool): True if this is the first page, False otherwise.
        is_last (bool): True if this is the last page, False otherwise.
    """

    content: list[Any]
    is_first: bool
    is_last: bool


class Page(BasePage):
    """
    Represents a single page in offset-based pagination.

    Attributes:
        current_page (int): The current page number. Defaults to 1.
        next_page (int | None): The next page number, or None if it's the last page.
        previous_page (int | None): The previous page number, or None if it's the first page.
    """

    current_page: int = 1
    next_page: int | None
    previous_page: int | None


PageType = TypeVar("PageType", bound=BasePage)


class BasePaginator(Generic[PageType]):
    """
    A generic base class for paginators.

    This class provides common pagination functionalities and manages the queryset,
    page size, and ordering.

    Args:
        queryset (QuerySet): The queryset to paginate.
        page_size (int): The maximum number of items per page.
        next_item_attr (str): The attribute to link to the next item in the page.
                              Useful for chained lists or linked items. Defaults to "".
        previous_item_attr (str): The attribute to link to the previous item in the page.
                                  Useful for chained lists or linked items. Defaults to "".

    Raises:
        ValueError: If `page_size` is negative or if the `queryset` does not have an `order_by` clause.
    """

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
        """
        Clears all internal caches associated with the paginator, including page caches
        and the queryset's cache. Resets the reverse paginator.
        """
        self._page_cache.clear()
        self.queryset.all(clear_cache=True)
        if self._reverse_paginator:
            self._reverse_paginator = None

    async def get_amount_pages(self) -> int:
        """
        Calculates the total number of pages based on the total count of items
        and the page size.

        Returns:
            int: The total number of pages. Returns 1 if `page_size` is 0.
        """
        if not self.page_size:
            return 1
        count, remainder = divmod(await self.get_total(), self.page_size)
        return count + (1 if remainder else 0)

    async def get_total(self) -> int:
        """
        Retrieves the total number of items in the queryset.

        Returns:
            int: The total count of items.
        """
        return await self.queryset.count()

    async def get_page(self) -> PageType:
        """
        Abstract method to get a specific page of results.

        This method must be implemented by subclasses.

        Raises:
            NotImplementedError: This method is not implemented in the base class.
        """
        raise NotImplementedError()

    def shall_drop_first(self, is_first: bool) -> bool:
        """
        Determines if the first item fetched should be dropped.

        This is typically relevant when using `previous_item_attr` to link items
        and fetching a page that is not the very first one, where the first item
        in the raw fetch might be the last item of the *previous* page.

        Args:
            is_first (bool): True if the current page is considered the very first page, False otherwise.

        Returns:
            bool: True if the first item should be dropped, False otherwise.
        """
        return bool(self.next_item_attr and not is_first)

    def convert_to_page(self, inp: Iterable, /, is_first: bool, reverse: bool = False) -> PageType:
        """
        Converts an iterable of raw items into a `BasePage` (or a subclass thereof).

        This method handles linking items using `next_item_attr` and `previous_item_attr`
        and determines `is_first` and `is_last` properties of the page.

        Args:
            inp (Iterable): An iterable of items to be paginated.
            is_first (bool): True if this is the first page of results, False otherwise.
            reverse (bool): True if the items are being processed in reverse order, False otherwise.

        Returns:
            PageType: An instance of `BasePage` or its subclass containing the paginated content.
        """
        last_item: Any = None
        drop_first = self.shall_drop_first(is_first)
        result_list = []
        item_counter = 0
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
            return cast(
                PageType, BasePage(content=result_list, is_first=is_last, is_last=is_first)
            )
        else:
            return cast(
                PageType, BasePage(content=result_list, is_first=is_first, is_last=is_last)
            )

    async def paginate_queryset(
        self, queryset: QuerySet, is_first: bool = True, prefill: Iterable | None = None
    ) -> AsyncGenerator[BasePage, None]:
        """
        Asynchronously paginates a given queryset, yielding `BasePage` objects.

        This is an internal helper method used by concrete paginator implementations.
        It handles the core logic of fetching items in chunks and assembling them into pages.

        Args:
            queryset (QuerySet): The queryset to paginate.
            is_first (bool): True if this is the very first chunk being processed, False otherwise.
                             Defaults to True.
            prefill (Iterable | None): An optional iterable of items to prepend to the first page's content.
                                      Useful for handling boundary conditions in cursor-based pagination.
                                      Defaults to None.

        Yields:
            AsyncGenerator[BasePage, None]: An asynchronous generator that yields `BasePage` objects.
        """
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
                    page = BasePaginator.convert_to_page(self, container, is_first=is_first)
                    yield page
                    if self.previous_item_attr and is_first:
                        min_size += 1
                    is_first = False
                    container = [page.content[-1], item] if self.previous_item_attr else [item]
        else:
            async for item in queryset:
                container.append(item)
                if self.page_size and len(container) >= min_size:
                    page = BasePaginator.convert_to_page(self, container, is_first=is_first)
                    yield page
                    if self.previous_item_attr and is_first:
                        min_size += 1
                    is_first = False
                    container = [page.content[-1], item] if self.previous_item_attr else [item]
        if page is None or not page.is_last:
            yield BasePaginator.convert_to_page(self, container, is_first=is_first)

    async def paginate(self) -> AsyncGenerator[PageType, None]:
        """
        Abstract method for concrete paginators to implement their specific pagination logic.

        This asynchronous generator should yield `PageType` objects.

        Raises:
            NotImplementedError: This method is not implemented in the base class.
        """
        raise NotImplementedError()

    def get_reverse_paginator(self) -> Self:
        """
        Returns a paginator instance that traverses the queryset in reverse order.

        This is useful for implementing backward pagination. The reverse paginator
        shares caches for efficiency.

        Returns:
            Self: A new paginator instance configured for reverse traversal.
        """
        if self._reverse_paginator is None:
            self._reverse_paginator = type(self)(
                self.queryset.reverse(),
                page_size=self.page_size,
                next_item_attr=self.next_item_attr,
                previous_item_attr=self.previous_item_attr,
            )
            self._reverse_paginator._reverse_paginator = self
        return self._reverse_paginator


class Paginator(BasePaginator[Page]):
    """
    A concrete paginator implementation for traditional offset-based pagination.

    This paginator returns `Page` objects with explicit `current_page`, `next_page`,
    and `previous_page` numbers.
    """

    async def paginate(self, start_page: int = 1) -> AsyncGenerator[Page, None]:
        """
        Paginates through the queryset using offset and limit, yielding `Page` objects.

        Args:
            start_page (int): The page number to start pagination from. Defaults to 1.

        Yields:
            AsyncGenerator[Page, None]: An asynchronous generator that yields `Page` objects.
        """
        query = self.queryset
        if start_page > 1:
            offset = self.page_size * (start_page - 1)
            if self.previous_item_attr:
                offset = max(offset - 1, 0)
            if offset > 0:
                query = query.offset(offset)
        counter = 1
        async for page_obj in self.paginate_queryset(query, is_first=start_page == 1):
            yield Page(
                **page_obj.__dict__,
                next_page=None if page_obj.is_last else counter + 1,
                previous_page=None if page_obj.is_first else counter - 1,
                current_page=counter,
            )
            counter += 1

    def convert_to_page(
        self, inp: Iterable, /, page: int, is_first: bool, reverse: bool = False
    ) -> Page:
        """
        Converts an iterable of items into a `Page` object, specifically for offset-based pagination.

        This method extends the base `convert_to_page` by adding page number information.

        Args:
            inp (Iterable): The input iterable of items to convert into a page.
            page (int): The current page number.
            is_first (bool): True if this is considered the first page, False otherwise.
            reverse (bool): True if the pagination is in reverse order, False otherwise.

        Returns:
            Page: The created Page object.
        """
        page_obj: BasePage = super().convert_to_page(
            inp,
            is_first=is_first,
            reverse=reverse,
        )
        return Page(
            **page_obj.__dict__,
            current_page=page,
            next_page=None if page_obj.is_last else page + 1,
            previous_page=None if page_obj.is_first else page + 1,
        )

    async def _get_page(self, page: int, reverse: bool = False) -> Page:
        """
        Internal method to fetch a specific page of results based on page number.

        This method handles calculating the offset and limit for the database query.

        Args:
            page (int): The page number to fetch.
            reverse (bool): True if fetching the page in reverse order, False otherwise.

        Returns:
            Page: The requested page of results.
        """
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
            return self.convert_to_page(
                resultarr, page=page, is_first=offset == 0, reverse=reverse
            )
        query = self.queryset
        query = query.offset(offset)
        if self.page_size:
            query = query.limit(self.page_size + 1)
        return self.convert_to_page(await query, page=page, is_first=offset == 0, reverse=reverse)

    async def get_page(self, page: int = 1) -> Page:
        """
        Retrieves a specific page of results by its page number.

        Results are cached for subsequent requests.

        Args:
            page (int): The page number to retrieve. Defaults to 1.

        Returns:
            Page: The requested page of results.

        Raises:
            ValueError: If the `page` parameter is invalid (e.g., 0 or not an integer).
        """
        if page == 0 or not isinstance(page, int):
            raise ValueError(f"Invalid page parameter value: {page!r}")
        if self.page_size == 0:
            # for caching, there are no other pages, this does not apply to cursor!
            page = 1
        if page in self._page_cache:
            return self._page_cache[page]
        page_obj = await self._get_page(page=page)

        self._page_cache[page] = page_obj
        return page_obj
