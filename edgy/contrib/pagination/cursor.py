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

    This class extends the `BasePage` to include specific attributes
    relevant to cursor-based navigation, namely the `next_cursor`
    for fetching subsequent pages and `current_cursor` that was used
    to retrieve the current page.

    Attributes:
        next_cursor (Hashable | None): The cursor identifier that can be
            used to fetch the page immediately following the current page.
            It is `None` if this is the last page.
        current_cursor (Hashable | None): The cursor identifier that was
            used as the starting point to fetch the current page. It is
            `None` if the current page is the very first page of the dataset.
    """

    next_cursor: Hashable | None
    current_cursor: Hashable | None


class CursorPaginator(BasePaginator[CursorPage]):
    """
    A paginator that implements cursor-based pagination.

    This paginator provides an efficient way to navigate through large datasets
    without relying on traditional offset/limit, which can be inefficient for
    deep pagination. Instead, it uses a cursor (typically derived from the
    ordering fields of the last item on a page) to define the starting point
    for fetching the next or previous set of results.

    Args:
        queryset (QuerySet): The queryset to paginate. This queryset
            **must** have an `order_by` clause defined, as cursors are
            derived from these ordering fields.
        page_size (int): The maximum number of items to retrieve per page.
        next_item_attr (str): The name of the attribute on model instances
            that will be used to store a reference to the 'next' item in the
            logical sequence across pages. This is for client-side linking.
            Defaults to an empty string.
        previous_item_attr (str): The name of the attribute on model instances
            that will be used to store a reference to the 'previous' item in the
            logical sequence across pages. This is for client-side linking.
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
        # Cache for pages fetched in reverse order.
        self._reverse_page_cache: dict[Hashable, CursorPage] = {}
        # The search vector is computed based on the queryset's ordering,
        # used to construct cursor-based WHERE clauses.
        self.search_vector = self.calculate_search_vector()

    def calculate_search_vector(self) -> tuple[str, ...]:
        """
        Calculates the search vector used for filtering based on the `order_by` criteria.

        The search vector constructs a tuple of filter strings (e.g., "id__gte", "name__lt")
        from the `order_by` fields. This is crucial for building the WHERE clause that
        enables cursor-based pagination, determining how to fetch items strictly after
        (or before, for reverse) a given cursor. For all but the last ordering criterion,
        `__gte` (or `__lte` for descending) is used, and for the last criterion,
        `__gt` (or `__lt` for descending) is used to ensure strict ordering and avoid duplicates.

        Returns:
            tuple[str, ...]: A tuple of strings representing the search vector,
            ready to be used in a `filter()` operation with corresponding cursor values.
        """
        # For all but the last ordering criteria, use >= (or <= for descending).
        vector = [
            f"{criteria[1:]}__lte" if criteria.startswith("-") else f"{criteria}__gte"
            for criteria in self.order_by[:-1]
        ]
        # For the last ordering criterion, use > (or < for descending) for strict progression.
        criteria = self.order_by[-1]
        vector.append(f"{criteria[1:]}__lt" if criteria.startswith("-") else f"{criteria}__gt")

        return tuple(vector)

    def cursor_to_vector(self, cursor: Hashable) -> tuple[Hashable, ...]:
        """
        Converts a single cursor value or a tuple of cursor values into a vector (tuple).

        This is necessary because `order_by` can define multiple fields, requiring
        a composite cursor. If the `order_by` only has one field, a single cursor
        value is wrapped in a tuple.

        Args:
            cursor (Hashable): The cursor value to convert. It can be a single
                hashable value or an existing tuple of hashable values.

        Returns:
            tuple[Hashable, ...]: The cursor represented as a tuple (vector),
            suitable for use with the `search_vector`.

        Raises:
            AssertionError: If `order_by` has more than one element and a
                non-tuple `cursor` is provided, indicating an inconsistency.
        """
        if isinstance(cursor, tuple):
            return cursor
        # If order_by has multiple fields but a single cursor is provided, it's an error.
        assert len(self.order_by) == 1, (
            "Cannot convert single cursor to vector when order_by has multiple fields. "
            "Expected a tuple for cursor."
        )
        return (cursor,)

    def vector_to_cursor(self, vector: tuple[Hashable, ...]) -> Hashable:
        """
        Converts a cursor vector (tuple) back into a single cursor value or a tuple.

        This method is the inverse of `cursor_to_vector`. If the `order_by`
        criteria used to create the vector involved multiple fields, the vector
        is returned as a tuple. Otherwise, only the single element of the vector
        is returned.

        Args:
            vector (tuple[Hashable, ...]): The cursor vector to convert.

        Returns:
            Hashable: The cursor value, either a single hashable or a tuple of hashables.
        """
        if len(self.order_by) > 1:
            return vector
        return vector[0]

    def obj_to_vector(self, obj: Any) -> tuple:
        """
        Converts a model instance into a cursor vector.

        This is achieved by extracting the values of the fields specified in the
        paginator's `order_by` criteria from the given model object. The order of
        values in the resulting tuple corresponds to the order of fields in `order_by`.

        Args:
            obj (Any): The model instance from which to extract cursor values.

        Returns:
            tuple: A tuple representing the cursor vector for the object,
            derived from its `order_by` field values.
        """
        # Extract attribute values in the order specified by `self.order_by`.
        # `lstrip("-")` removes any leading '-' used for descending order.
        return tuple(getattr(obj, attr.lstrip("-")) for attr in self.order_by)

    def obj_to_cursor(self, obj: Any) -> Hashable:
        """
        Converts a model instance into a single cursor (or a tuple of cursors).

        This method acts as a convenience wrapper that first transforms the
        model object into a vector using `obj_to_vector` and then converts
        that vector into the final cursor format using `vector_to_cursor`.

        Args:
            obj (Any): The model instance to convert into a cursor.

        Returns:
            Hashable: The cursor (single value or tuple) representing the
            object's position based on the pagination's `order_by` fields.
        """
        return self.vector_to_cursor(self.obj_to_vector(obj))

    def clear_caches(self) -> None:
        """
        Clears all internal caches used by the paginator.

        This includes the base paginator's caches (page cache and queryset cache)
        as well as the specific `_reverse_page_cache` used by `CursorPaginator`.
        Calling this ensures that all subsequent pagination requests will fetch
        fresh data from the database.
        """
        super().clear_caches()
        self._reverse_page_cache.clear()

    def convert_to_page(
        self, inp: Iterable, /, cursor: Hashable | None, is_first: bool, reverse: bool = False
    ) -> CursorPage:
        """
        Converts an iterable of items (raw query results) into a `CursorPage` object.

        This method extends the base `convert_to_page` by explicitly setting
        `next_cursor` and `current_cursor` attributes on the resulting page.
        It uses the last item in the content to determine the `next_cursor`.

        Args:
            inp (Iterable): The input iterable of items to convert into a page.
            cursor (Hashable | None): The cursor that was used to fetch this
                specific page. It will be set as `current_cursor` on the `CursorPage`.
                `None` if fetching the very first page.
            is_first (bool): True if this is considered the first logical page
                of the entire dataset, False otherwise. This affects the `is_first`
                attribute of the `CursorPage`.
            reverse (bool): True if the items are being processed in reverse order
                (e.g., for backward pagination), False otherwise.

        Returns:
            CursorPage: The created `CursorPage` object, containing the paginated
            content and cursor information.
        """
        # Call the base paginator's method to get the common page structure.
        page_obj: BasePage = super().convert_to_page(
            inp,
            is_first=is_first,
            reverse=reverse,
        )
        # Determine the `next_cursor` from the last item of the current page's content.
        # If the page is empty, `next_cursor` will be None.
        next_cursor = self.obj_to_cursor(page_obj.content[-1]) if page_obj.content else None
        # Construct and return the `CursorPage` with additional cursor information.
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

        This method is crucial for determining if a "previous" page exists
        or if the current page is indeed the "first" when navigating backward
        or checking boundaries in cursor-based pagination. It queries the
        reversed queryset to find the single item directly preceding the cursor.

        Args:
            cursor (Hashable): The cursor value from which to look for the
                immediately preceding item.

        Returns:
            list["BaseModelType"]: A list containing the extra item found
            before the cursor, or an empty list if no such item exists.
        """
        # Convert the hashable cursor into its tuple representation (vector).
        vector = self.cursor_to_vector(cursor)
        # Get the reverse paginator instance to query items in reverse order.
        rpaginator = self.get_reverse_paginator()
        # Filter the reversed queryset using the search vector (appropriate for reverse lookup)
        # and limit to 1 to get only the immediate preceding item.
        return await rpaginator.queryset.filter(
            **dict(zip(rpaginator.search_vector, vector, strict=False))
        ).limit(1)

    async def exists_extra_before(self, cursor: Hashable) -> bool:
        """
        Checks if there exists an extra item immediately before the given cursor.

        This is a more efficient check than `get_extra_before` if only the
        existence (and not the item itself) is needed.

        Args:
            cursor (Hashable): The cursor to check for preceding items.

        Returns:
            bool: True if at least one item exists immediately before the cursor,
            False otherwise.
        """
        # Convert the hashable cursor into its tuple representation (vector).
        vector = self.cursor_to_vector(cursor)
        # Get the reverse paginator instance.
        rpaginator = self.get_reverse_paginator()
        # Use `exists()` on the filtered reversed queryset for an efficient check.
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
        Internal method to fetch a page of results starting *after* a given cursor vector.

        This method encapsulates the core logic for fetching a page in a forward
        direction using a cursor. It handles applying filters based on the cursor,
        determining if the page is the "first", and optionally injecting extra
        items for boundary conditions (e.g., when linking items).

        Args:
            vector (tuple[Hashable, ...] | None): The cursor vector (tuple)
                representing the starting point for the query. If `None`,
                it fetches the very first items from the beginning of the dataset.
            injected_extra (list[BaseModelType] | None): An optional list of
                `BaseModelType` instances to prepend to the fetched content.
                This is typically used when fetching backward pages to include
                the preceding item.
            reverse (bool): True if the internal processing is for a reverse
                pagination flow (e.g., when this method is called by `get_page_before`),
                False otherwise. This affects `convert_to_page` behavior.

        Returns:
            tuple[CursorPage, list[BaseModelType]]: A tuple containing:
                - `CursorPage`: The constructed page object.
                - `list[BaseModelType]`: The raw list of items that were fetched
                  from the database (including any injected extra items).
        """
        # Apply limit to fetch page_size + 1 items to check for next page existence.
        query = self.queryset.limit(self.page_size + 1) if self.page_size else self.queryset
        if vector is not None:
            # Apply cursor-based filtering using the calculated search vector.
            query = query.filter(**dict(zip(self.search_vector, vector, strict=False)))

        # Determine if this is the logical first page.
        is_first = vector is None

        resultarr: list[BaseModelType]
        # If not the first page and previous_item_attr is used,
        # fetch the item immediately before the current cursor.
        if not is_first and self.previous_item_attr:
            # Use `injected_extra` if provided, otherwise fetch it.
            resultarr = (
                await self.get_extra_before(self.vector_to_cursor(vector))
                if injected_extra is None
                else injected_extra
            )
            # If no item exists before, it means this is effectively the first page.
            if not resultarr:
                is_first = True
            resultarr.extend(await query)  # Extend with items from the main query.
        elif injected_extra is not None:
            # If extra items are explicitly injected, set `is_first` to False
            # if `injected_extra` is not empty (meaning there are items before).
            if injected_extra:
                is_first = False
            injected_extra.extend(await query)
            resultarr = injected_extra
        else:
            # If no cursor or no previous item logic, check for existence of extra before.
            if not is_first and not await self.exists_extra_before(self.vector_to_cursor(vector)):
                is_first = True
            resultarr = await query

        # Convert the collected items into a CursorPage object.
        page_obj = self.convert_to_page(
            resultarr,
            # Set current_cursor to None if it's truly the first page.
            cursor=None if vector is None else self.vector_to_cursor(vector),
            is_first=is_first,
            reverse=reverse,
        )
        return page_obj, resultarr

    async def get_page_after(self, cursor: Hashable | None = None) -> CursorPage:
        """
        Retrieves the page of results immediately following the given cursor.

        If no `cursor` is provided, this method fetches the very first page
        of the dataset. The fetched page is also cached for subsequent requests.

        Args:
            cursor (Hashable | None): The cursor from which to start fetching.
                If `None`, pagination starts from the beginning of the dataset.

        Returns:
            CursorPage: The page of results immediately following (or starting from)
            the specified cursor.
        """
        vector: tuple[Hashable, ...] | None = None
        if cursor is not None:
            # Convert the hashable cursor to its vector representation.
            vector = self.cursor_to_vector(cursor)

        # Check if the page for this vector is already in the forward page cache.
        if vector in self._page_cache:
            page_obj = self._page_cache[vector]
            return page_obj

        # If not in cache, fetch the page using the internal `_get_page_after` method.
        page_obj = (await self._get_page_after(vector=vector))[0]
        # Store the fetched page in the cache.
        self._page_cache[vector] = page_obj
        return page_obj

    async def get_page_before(self, cursor: Hashable | None = None) -> CursorPage:
        """
        Retrieves the page of results immediately preceding the given cursor.

        This method effectively implements backward pagination. If no `cursor`
        is provided, it fetches the "last" page of the dataset when traversed
        in reverse order. The fetched page is also cached for subsequent requests.

        Args:
            cursor (Hashable | None): The cursor to start fetching backward from.
                If `None`, it fetches the "last" page in reverse order.

        Returns:
            CursorPage: The page of results immediately preceding (or ending at)
            the specified cursor.
        """
        vector: tuple[Hashable, ...] | None = None
        if cursor is not None:
            # Convert the hashable cursor to its vector representation.
            vector = self.cursor_to_vector(cursor)

        # Check if the page for this vector is already in the reverse page cache.
        if vector in self._reverse_page_cache:
            page_obj = self._reverse_page_cache[vector]
            return page_obj

        # Get the reverse paginator instance.
        reverse_paginator = self.get_reverse_paginator()
        new_vector: tuple[Hashable, ...] | None = None

        # To correctly match cursors when going backward, we often need to fetch
        # one extra item that is immediately before the current starting point
        # in the *reversed* sequence. This item will become the "first" item
        # of the backward page.
        injected_reverse = (
            await reverse_paginator.get_extra_before(vector) if vector is not None else []
        )

        # If an item was found before in the reverse direction, its vector
        # becomes the new starting point for the `_get_page_after` call on the
        # reverse paginator.
        if injected_reverse:
            new_vector = self.obj_to_vector(injected_reverse[0])

        # Fetch the page using the reverse paginator's `_get_page_after` method.
        # We pass `injected_extra` to ensure the correct starting point for the backward page.
        # `reverse=True` indicates to `convert_to_page` that it's processing in reverse order.
        reverse_page, raw_array = await reverse_paginator._get_page_after(
            new_vector, injected_extra=injected_reverse, reverse=True
        )

        # Construct the `CursorPage` object for the "before" page.
        page_obj = CursorPage(
            content=reverse_page.content,  # Content is the reversed list from `reverse_page`.
            is_first=reverse_page.is_first,  # `is_first` for the reverse page becomes `is_last` for forward.
            is_last=reverse_page.is_last,  # `is_last` for the reverse page becomes `is_first` for forward.
            next_cursor=self.obj_to_cursor(raw_array[-1])
            if raw_array
            else None,  # The next cursor is from the last item of the raw fetched array.
            current_cursor=None
            if vector is None
            else self.vector_to_cursor(vector),  # The current cursor is the input cursor.
        )
        # Cache the fetched page in the reverse page cache.
        self._reverse_page_cache[vector] = reverse_page
        return page_obj

    async def get_page(self, cursor: Hashable | None = None, backward: bool = False) -> CursorPage:
        """
        Retrieves a page of results, either forward or backward from a given cursor.

        This method serves as the main public interface for fetching a cursor-based page.
        It dispatches the call to either `get_page_after` (for forward pagination)
        or `get_page_before` (for backward pagination) based on the `backward` flag.

        Args:
            cursor (Hashable | None): The cursor to start fetching from.
                If `None`, it fetches the first page (or the "last" page if `backward` is True).
            backward (bool): If `True`, fetches the page preceding the `cursor`.
                If `False` (default), fetches the page following the `cursor`.

        Returns:
            CursorPage: The requested page of results, including its content and
            cursor information.
        """
        # If `backward` is True, fetch the page before the given cursor.
        if backward:
            return await self.get_page_before(cursor)
        # Otherwise, fetch the page after the given cursor.
        else:
            return await self.get_page_after(cursor)

    async def paginate(
        self, start_cursor: Hashable | None = None, stop_cursor: Hashable | None = None
    ) -> AsyncGenerator[CursorPage, None]:
        """
        Paginates through the queryset using cursors, yielding `CursorPage` objects.

        This asynchronous generator allows for iterating over pages of results
        in a cursor-based manner. It can start from a specified `start_cursor`
        and continue yielding pages until a `stop_cursor` is reached (exclusive).

        Args:
            start_cursor (Hashable | None): The cursor from which to begin pagination.
                If `None`, pagination starts from the very beginning of the dataset.
            stop_cursor (Hashable | None): The cursor at which to cease pagination.
                Pages will be yielded up to, but not including, the page identified
                by this cursor. If `None`, pagination continues until the end of the dataset.

        Yields:
            AsyncGenerator[CursorPage, None]: An asynchronous generator that yields
            `CursorPage` objects, each representing a paginated chunk of data.
        """
        query = self.queryset
        prefill_container: list[Any] = []  # Used to store an extra item for linking.
        start_vector: tuple[Hashable, ...] | None = None

        if start_cursor is not None:
            # Convert the start cursor to its vector representation.
            start_vector = self.cursor_to_vector(start_cursor)
            # Apply cursor-based filtering to the queryset.
            query = query.filter(**dict(zip(self.search_vector, start_vector, strict=False)))
            # If `previous_item_attr` is used, try to fetch the item immediately before
            # the `start_cursor` to correctly determine `is_first` for the initial page.
            if self.previous_item_attr:
                prefill_container = await self.get_extra_before(start_cursor)

        if stop_cursor is not None:
            # If a `stop_cursor` is provided, apply a reverse filter to the queryset
            # to limit results up to that point.
            stop_vector = self.cursor_to_vector(stop_cursor)
            query = query.filter(
                **dict(zip(self.get_reverse_paginator().search_vector, stop_vector, strict=False))
            )

        # Initialize `current_cursor` for the yielded pages.
        current_cursor: Hashable | None = (
            None if start_vector is None else self.vector_to_cursor(start_vector)
        )

        # Iterate asynchronously over the chunks generated by `paginate_queryset`.
        async for page in self.paginate_queryset(
            query,
            # `is_first` is true if no start_cursor and no prefill_container (truly the beginning).
            is_first=bool(start_cursor is None and not prefill_container),
            prefill=prefill_container,
        ):
            # Determine the `next_cursor` from the last item of the current page.
            next_cursor = self.obj_to_cursor(page.content[-1]) if page.content else None
            # Yield the `CursorPage` with content, boundary info, and cursor details.
            yield CursorPage(
                **page.__dict__, next_cursor=next_cursor, current_cursor=current_cursor
            )
            # Update `current_cursor` for the next iteration to be the `next_cursor` of this page.
            current_cursor = next_cursor
