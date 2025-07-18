from math import ceil
from typing import Any


class NumberedPaginator:
    """
    A paginator class for dividing a list of items into numbered pages.
    Attributes:
        queryset (list[Any]): The list of items to paginate.
        page (int): The current page number (1-based).
        page_size (int): The number of items per page.
        total_items (int): The total number of items in the queryset.
        total_pages (int): The total number of pages.
    Args:
        queryset (list[Any]): The list of items to paginate.
        page (int, optional): The page number to retrieve. Defaults to 1.
        page_size (int, optional): The number of items per page. Defaults to 10.
    Methods:
        get_paginated_response() -> dict[str, Any]:
            Returns a dictionary containing pagination metadata and the items for the current page.
            Returns:
                dict[str, Any]: A dictionary with the following keys:
                    - "count": Total number of items.
                    - "total_pages": Total number of pages.
                    - "current_page": The current page number.
                    - "page_size": The number of items per page.
                    - "results": The list of items for the current page.
    """

    def __init__(self, queryset: list[Any], page: int = 1, page_size: int = 10):
        """
        Initializes the pagination object with the provided queryset, page number, and page size.
        Args:
            queryset (list[Any]): The list of items to paginate.
            page (int, optional): The current page number (1-based). Defaults to 1. Values less than 1 are set to 1.
            page_size (int, optional): The number of items per page. Defaults to 10.
        Attributes:
            queryset (list[Any]): The original list of items to paginate.
            page (int): The current page number, always at least 1.
            page_size (int): The number of items per page.
            total_items (int): The total number of items in the queryset.
            total_pages (int): The total number of pages, calculated based on total_items and page_size.
        Raises:
            ValueError: If page_size is less than or equal to zero.
        Notes:
            The total_pages attribute is computed using the ceiling of total_items divided by page_size.
        """

        self.queryset = queryset
        self.page = max(page, 1)
        self.page_size = page_size
        self.total_items = len(queryset)
        self.total_pages = ceil(self.total_items / page_size)

    def get_paginated_response(self) -> dict[str, Any]:
        """
        Generate a paginated response containing metadata and the current page's items.
        Returns:
            dict[str, Any]: A dictionary with the following keys:
                - "count" (int): The total number of items across all pages.
                - "total_pages" (int): The total number of pages available.
                - "current_page" (int): The current page number (1-based index).
                - "page_size" (int): The number of items per page.
                - "results" (list): The list of items for the current page.
        Notes:
            - The method slices the queryset according to the current page and page size.
            - Assumes that `self.queryset`, `self.page`, `self.page_size`, `self.total_items`, and
            `self.total_pages` are defined and valid.
            - Useful for APIs that require paginated data responses.
        """

        start = (self.page - 1) * self.page_size
        end = start + self.page_size
        items = self.queryset[start:end]

        return {
            "count": self.total_items,
            "total_pages": self.total_pages,
            "current_page": self.page,
            "page_size": self.page_size,
            "results": items,
        }
