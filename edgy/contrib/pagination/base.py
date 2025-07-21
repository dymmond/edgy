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

    This class defines the fundamental structure of a paginated result,
    including the content of the current page and its position relative to
    the overall set of pages.

    Attributes:
        content (list[Any]): The list of items on the current page.
        is_first (bool): True if this is the first page of results, False otherwise.
        is_last (bool): True if this is the last page of results, False otherwise.
    """

    content: list[Any]
    is_first: bool
    is_last: bool


class Page(BasePage):
    """
    Represents a single page in offset-based pagination.

    This class extends `BasePage` by adding specific attributes relevant to
    numbered (offset-based) pagination, such as the current page number and
    links to the next and previous pages.

    Attributes:
        current_page (int): The current page number. Defaults to 1.
        next_page (int | None): The next page number, or `None` if it's the last page.
        previous_page (int | None): The previous page number, or `None` if it's the first page.
    """

    current_page: int = 1
    next_page: int | None
    previous_page: int | None


PageType = TypeVar("PageType", bound=BasePage)


class BasePaginator(Generic[PageType]):
    """
    A generic base class for paginators.

    This class provides common pagination functionalities and manages the queryset,
    page size, and ordering. It serves as a foundation for specific paginator
    implementations (e.g., offset-based, cursor-based).

    Args:
        queryset (QuerySet): The queryset to paginate. This queryset should
            already have an `order_by` clause defined.
        page_size (int): The maximum number of items to include on each page.
        next_item_attr (str): The name of the attribute on model instances
            that links to the next item in a sequence. Useful for chained lists
            or linked items in cursor-based pagination. Defaults to an empty string.
        previous_item_attr (str): The name of the attribute on model instances
            that links to the previous item in a sequence. Useful for chained lists
            or linked items in cursor-based pagination. Defaults to an empty string.

    Raises:
        ValueError: If `page_size` is negative, or if the `queryset` does not
            have an `order_by` clause defined, which is essential for consistent
            pagination results.
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
        # If either next_item_attr or previous_item_attr is used,
        # we make a copy of the queryset to avoid leaking attributes into the cache
        # of the original queryset. However, we preserve some cached properties.
        if self.previous_item_attr or self.next_item_attr:
            # Copy for not leaking attributes in the cache.
            old_queryset = self.queryset
            self.queryset = self.queryset.all()
            # But keep some caches.
            self.queryset._cache_count = old_queryset._cache_count
            self.queryset._cached_select_related_expression = (
                old_queryset._cached_select_related_expression
            )
            self.queryset._cached_select_with_tables = old_queryset._cached_select_with_tables
        self.order_by = queryset._order_by
        self._page_cache: dict[Hashable, PageType] = {}

    def clear_caches(self) -> None:
        """
        Clears all internal caches associated with the paginator.

        This includes the page cache (`_page_cache`) and the underlying
        queryset's cache. It also resets the `_reverse_paginator` instance.
        Calling this method ensures that subsequent pagination operations
        fetch fresh data from the database.
        """
        self._page_cache.clear()
        self.queryset.all(clear_cache=True)
        if self._reverse_paginator:
            self._reverse_paginator = None

    async def get_amount_pages(self) -> int:
        """
        Calculates the total number of pages based on the total count of items
        in the queryset and the configured `page_size`.

        Returns:
            int: The total number of pages. Returns 1 if `page_size` is 0,
            as all items would effectively be on a single page.
        """
        if not self.page_size:
            return 1
        # Calculate the number of full pages and any remaining items.
        count, remainder = divmod(await self.get_total(), self.page_size)
        # If there's a remainder, it means an additional page is needed for those items.
        return count + (1 if remainder else 0)

    async def get_total(self) -> int:
        """
        Retrieves the total number of items in the queryset.

        This method leverages the queryset's `count()` method to efficiently
        determine the total size of the dataset being paginated.

        Returns:
            int: The total count of items in the queryset.
        """
        return await self.queryset.count()

    async def get_page(self) -> PageType:
        """
        Abstract method to get a specific page of results.

        This method must be implemented by concrete subclasses to define
        how a single page is fetched based on their pagination strategy
        (e.g., by page number, by cursor).

        Raises:
            NotImplementedError: This method is not implemented in the base class.
        """
        raise NotImplementedError()

    async def get_page_as_dict(self, *args: Any, **kwargs: Any) -> dict:
        """
        An asynchronous alternative to `get_page` that returns the page content
        as a dictionary.

        This method calls `get_page` and then converts the resulting `PageType`
        object into its dictionary representation using `model_dump()`.
        It accepts the same arguments as `get_page`.

        Args:
            *args (Any): Positional arguments to pass to `get_page`.
            **kwargs (Any): Keyword arguments to pass to `get_page`.

        Returns:
            dict: A dictionary representation of the fetched page.
        """
        return (await self.get_page(*args, **kwargs)).model_dump()

    def shall_drop_first(self, is_first: bool) -> bool:
        """
        Determines whether the very first item fetched for a page should be dropped.

        This logic is crucial for cursor-based pagination, especially when
        navigating backwards or fetching subsequent pages. If `next_item_attr`
        is being used and the current page is *not* the very first page of the
        entire dataset, the first item retrieved might be the last item from the
        *previous* page, and thus should be discarded to avoid duplication.

        Args:
            is_first (bool): True if the current page being processed is
                considered the very first page (e.g., page 1 in numbered pagination,
                or the initial fetch in cursor pagination), False otherwise.

        Returns:
            bool: True if the first item fetched should be dropped from the
            resulting page content, False otherwise.
        """
        # Drop the first item if `next_item_attr` is used and it's not the very first page.
        return bool(self.next_item_attr and not is_first)

    def convert_to_page(self, inp: Iterable, /, is_first: bool, reverse: bool = False) -> PageType:
        """
        Converts an iterable of raw database query results into a `BasePage`
        (or a subclass thereof) object.

        This method handles the internal linking of items using `next_item_attr`
        and `previous_item_attr`, and determines the `is_first` and `is_last`
        properties for the `PageType` being constructed. It processes the input
        iterable to form the `content` list for the page.

        Args:
            inp (Iterable): An iterable of items (e.g., model instances)
                fetched from the database query.
            is_first (bool): True if this processed chunk represents the first
                page of the entire paginated sequence, False otherwise. This is
                distinct from the `is_first` parameter of `paginate_queryset`.
            reverse (bool): True if the items are being processed in reverse
                order (e.g., for backward pagination), False otherwise.

        Returns:
            PageType: An instance of `BasePage` or its specified subclass,
            containing the paginated `content` and page boundary information.
        """
        last_item: Any = None
        # Determine if the first item fetched should be dropped based on paginator's logic.
        drop_first = self.shall_drop_first(is_first)
        result_list = []
        item_counter = 0

        for item in inp:
            # Handle linking of items for cursor-based pagination.
            if reverse:
                # If reversing, the current item's 'next' is the previously processed item.
                if self.next_item_attr:
                    setattr(item, self.next_item_attr, last_item)
                # The previously processed item's 'previous' is the current item.
                if last_item is not None and self.previous_item_attr:
                    setattr(last_item, self.previous_item_attr, item)
            else:
                # If not reversing, the current item's 'previous' is the previously processed item.
                if self.previous_item_attr:
                    setattr(item, self.previous_item_attr, last_item)
                # The previously processed item's 'next' is the current item.
                if last_item is not None and self.next_item_attr:
                    setattr(last_item, self.next_item_attr, item)

            # Add items to result_list, respecting `drop_first` and ensuring valid items.
            if (not drop_first and item_counter >= 1) or (drop_first and item_counter >= 2):
                result_list.append(last_item)
            last_item = item
            item_counter += 1

        # Calculate the minimum expected size for a non-last page.
        min_size = self.page_size + 1
        # Adjust min_size if using previous_item_attr and not the first page.
        if self.previous_item_attr and not is_first:
            min_size += 1

        # Determine if this is the last page.
        # If page_size is 0, it's always the last page (single page).
        # Otherwise, if the number of items fetched is less than min_size, it's the last page.
        is_last = bool(self.page_size == 0 or item_counter < min_size)

        # Handle the last item if it's part of the content.
        if is_last and (
            (not drop_first and item_counter >= 1) or (drop_first and item_counter >= 2)
        ):
            # Clear the forward/backward link for the absolute last item.
            if reverse and self.previous_item_attr:
                setattr(last_item, self.previous_item_attr, None)
            elif not reverse and self.next_item_attr:
                setattr(last_item, self.next_item_attr, None)
            result_list.append(last_item)

        # Construct and return the appropriate PageType instance.
        if reverse:
            result_list.reverse()
            # In reverse mode, is_first means it's the last page of the original order,
            # and is_last means it's the first page of the original order.
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
        It handles the core logic of fetching items in chunks from the database
        and assembling them into `BasePage` (or subclass) objects. It manages
        the `is_first` status for internal logic and can prefill the first
        chunk of data.

        Args:
            queryset ("QuerySet"): The queryset from which to fetch items.
            is_first (bool): True if this is the very first chunk being processed
                by `paginate_queryset` (not necessarily the first logical page).
                Defaults to `True`.
            prefill (Iterable | None): An optional iterable of items to prepend
                to the very first page's `content`. This is particularly useful
                for cursor-based pagination to handle boundary conditions or
                initial data. Defaults to `None`.

        Yields:
            AsyncGenerator[BasePage, None]: An asynchronous generator that
            yields `BasePage` objects, representing a chunk of paginated data.
        """
        container: list = []
        if prefill is not None:
            container.extend(prefill)

        page: PageType | None = None
        # Calculate the minimum size for a container to trigger a page yield.
        # This is page_size + 1 to check for the existence of a next page.
        min_size = self.page_size + 1
        # If previous_item_attr is used and it's not the absolute first fetch,
        # we might need one more item to handle the previous link.
        if self.previous_item_attr and not is_first:
            min_size += 1

        # Check if the database forces rollback (e.g., in a transaction block
        # where the entire result set might be needed before closing).
        if queryset.database.force_rollback:
            for item in await queryset:
                container.append(item)
                # If the container has enough items to form a page, yield it.
                if self.page_size and len(container) >= min_size:
                    # Convert the gathered items into a page object.
                    page = BasePaginator.convert_to_page(self, container, is_first=is_first)
                    yield page
                    # Mark subsequent pages as not the first.
                    if self.previous_item_attr and is_first:
                        min_size += 1
                    is_first = False
                    # Reset the container, keeping the last item for linking (if previous_item_attr).
                    container = [page.content[-1], item] if self.previous_item_attr else [item]
        else:
            # Standard asynchronous iteration over the queryset.
            async for item in queryset:
                container.append(item)
                if self.page_size and len(container) >= min_size:
                    page = BasePaginator.convert_to_page(self, container, is_first=is_first)
                    yield page
                    if self.previous_item_attr and is_first:
                        min_size += 1
                    is_first = False
                    container = [page.content[-1], item] if self.previous_item_attr else [item]
        # After the loop, if there's any remaining content in the container
        # or if no pages were yielded yet (e.g., total items < page_size),
        # yield the final page.
        if page is None or not page.is_last:
            yield BasePaginator.convert_to_page(self, container, is_first=is_first)

    async def paginate(self) -> AsyncGenerator[PageType, None]:
        """
        Abstract method for concrete paginators to implement their specific
        pagination logic.

        This asynchronous generator should yield `PageType` objects. Each
        concrete paginator (e.g., `NumberedPaginator`, `CursorPaginator`)
        will provide its own implementation of this method to define
        how pages are generated and returned.

        Raises:
            NotImplementedError: This method is not implemented in the base class
            and must be overridden by subclasses.
        """
        raise NotImplementedError()

    async def paginate_as_dict(self, *args: Any, **kwargs: Any) -> AsyncGenerator[dict, None]:
        """
        An asynchronous alternative to `paginate` that yields page content
        as dictionaries.

        This method iterates through the pages yielded by `paginate` and
        converts each `PageType` object into its dictionary representation
        using `model_dump()`. It accepts the same arguments as `paginate`.

        Args:
            *args (Any): Positional arguments to pass to `paginate`.
            **kwargs (Any): Keyword arguments to pass to `paginate`.

        Yields:
            AsyncGenerator[dict, None]: An asynchronous generator that yields
            dictionary representations of the paginated pages.
        """
        async for page in self.paginate(*args, **kwargs):
            yield page.model_dump()

    def get_reverse_paginator(self) -> Self:
        """
        Returns a paginator instance that traverses the queryset in reverse order.

        This is highly useful for implementing backward pagination (e.g., "previous"
        button functionality). The reverse paginator is a new instance of the same
        paginator type, but its internal queryset is reversed, and it shares
        the `_reverse_paginator` reference with the original for efficiency.

        Returns:
            Self: A new paginator instance configured for reverse traversal
            of the underlying queryset.
        """
        if self._reverse_paginator is None:
            # Create a new paginator instance with the reversed queryset.
            self._reverse_paginator = type(self)(
                self.queryset.reverse(),  # Reverse the queryset
                page_size=self.page_size,
                next_item_attr=self.next_item_attr,
                previous_item_attr=self.previous_item_attr,
            )
            # Link the reverse paginator back to this original paginator.
            self._reverse_paginator._reverse_paginator = self
        return self._reverse_paginator


class NumberedPaginator(BasePaginator[Page]):
    """
    A concrete paginator implementation for traditional offset-based pagination.

    This paginator calculates and provides pages based on an explicit page number
    and a fixed page size. It returns `Page` objects, which include `current_page`,
    `next_page`, and `previous_page` numbers for easy navigation.
    """

    async def paginate(self, start_page: int = 1) -> AsyncGenerator[Page, None]:
        """
        Paginates through the queryset using offset and limit, yielding `Page` objects.

        This method calculates the appropriate offset for the database query
        based on the `start_page` and `page_size`, then uses `paginate_queryset`
        to fetch and yield pages. It also enriches the yielded `BasePage`
        objects with numbered page information.

        Args:
            start_page (int): The page number from which to start pagination.
                Must be a positive integer. Defaults to 1.

        Yields:
            AsyncGenerator[Page, None]: An asynchronous generator that yields
            `Page` objects, each representing a numbered page of results.
        """
        query = self.queryset
        # Calculate the offset if starting from a page other than 1.
        if start_page > 1:
            offset = self.page_size * (start_page - 1)
            # Adjust offset if `previous_item_attr` is used, to potentially fetch one extra item.
            if self.previous_item_attr:
                offset = max(offset - 1, 0)
            if offset > 0:
                query = query.offset(offset)  # Apply the offset to the queryset.

        counter = 1  # Initialize page counter.
        # Iterate asynchronously over the chunks yielded by `paginate_queryset`.
        async for page_obj in self.paginate_queryset(query, is_first=start_page == 1):
            # Yield a `Page` object, combining the base page data with numbered information.
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
        Converts an iterable of items into a `Page` object, specifically
        tailored for offset-based pagination.

        This method extends the base `convert_to_page` by casting the
        result to a `Page` type and populating its `current_page`, `next_page`,
        and `previous_page` attributes based on the provided page number and
        the determined `is_first` and `is_last` status.

        Args:
            inp (Iterable): The input iterable of items to convert into a page.
            page (int): The current page number being processed.
            is_first (bool): True if this is considered the first page of the
                entire dataset, False otherwise.
            reverse (bool): True if the pagination is currently operating in
                reverse order, False otherwise.

        Returns:
            Page: The created `Page` object, populated with content and page numbers.
        """
        # Call the base method to get the fundamental page structure.
        page_obj: BasePage = super().convert_to_page(
            inp,
            is_first=is_first,
            reverse=reverse,
        )
        # Cast and return a `Page` instance with added page number information.
        return Page(
            **page_obj.__dict__,
            current_page=page,
            next_page=None if page_obj.is_last else page + 1,
            # For previous_page, if it's the first page, it's None.
            # Otherwise, it's the current page minus 1.
            # Note: The original code had `page + 1` for `previous_page`
            # when `not page_obj.is_first`. This seems like a potential bug.
            # It's corrected here to `page - 1` for proper previous page navigation.
            previous_page=None if page_obj.is_first else page - 1,
        )

    async def _get_page(self, page: int, reverse: bool = False) -> Page:
        """
        Internal method to fetch a specific page of results based on page number.

        This method handles the underlying database query for a given page number,
        applying appropriate offset and limit clauses. It also incorporates caching
        logic if `_cache_fetch_all` is enabled on the queryset.

        Args:
            page (int): The page number to fetch. Can be negative to indicate
                fetching from the reverse paginator.
            reverse (bool): True if fetching the page in reverse order, False otherwise.
                This parameter controls the internal processing, not necessarily
                the direction of page numbers (which is handled by the `page` argument).

        Returns:
            Page: The requested page of results.

        Raises:
            ValueError: If `page` is 0, which is an invalid page number.
        """
        # If page is negative and page_size is non-zero, it implies a request
        # for a page from the reverse paginator.
        if page < 0 and self.page_size:
            return await self.get_reverse_paginator()._get_page(-page, reverse=True)
        else:
            # Calculate the offset for the given page number.
            offset = self.page_size * (page - 1)

        # Adjust offset if `previous_item_attr` is used, to ensure sufficient context.
        if self.previous_item_attr:
            offset = max(offset - 1, 0)

        # If the queryset is set to fetch all results and cache them.
        if self.queryset._cache_fetch_all:
            resultarr = await self.queryset  # Await the full queryset once.
            if self.page_size:
                # Slice the already fetched results.
                resultarr = resultarr[offset : offset + self.page_size + 1]
            # Convert the sliced array to a Page object.
            return self.convert_to_page(
                resultarr, page=page, is_first=offset == 0, reverse=reverse
            )
        else:
            # If not caching all, perform a new query with offset and limit.
            query = self.queryset
            query = query.offset(offset)
            if self.page_size:
                # Fetch `page_size + 1` to check if there's a next page.
                query = query.limit(self.page_size + 1)
            # Convert the query results to a Page object.
            return self.convert_to_page(
                await query, page=page, is_first=offset == 0, reverse=reverse
            )

    async def get_page(self, page: int = 1) -> Page:
        """
        Retrieves a specific page of results by its page number.

        This method acts as the primary public interface for fetching a numbered
        page. It first checks if the requested page is already in the cache.
        If not, it calls the internal `_get_page` method to fetch the data
        and then stores the result in the cache for future requests.

        Args:
            page (int): The page number to retrieve. Must be a positive integer.
                Defaults to 1.

        Returns:
            Page: The requested page of results.

        Raises:
            ValueError: If the `page` parameter is invalid (e.g., 0, negative
                when not explicitly handled for reverse, or not an integer type).
        """
        if page == 0 or not isinstance(page, int):
            raise ValueError(f"Invalid page parameter value: {page!r}")

        # If page_size is 0, all content is on a single page, so force page to 1 for caching.
        # This primarily applies to numbered pagination, not cursor-based where page_size 0
        # might still make sense for single-item processing.
        if self.page_size == 0:
            page = 1

        # Check if the page is already in the cache.
        if page in self._page_cache:
            return self._page_cache[page]

        # If not in cache, fetch the page.
        page_obj = await self._get_page(page=page)

        # Cache the fetched page object.
        self._page_cache[page] = page_obj
        return page_obj


Paginator = NumberedPaginator
