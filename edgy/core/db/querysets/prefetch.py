from typing import TYPE_CHECKING, List, Optional, cast

from edgy.exceptions import QuerySetError

if TYPE_CHECKING:
    from edgy import QuerySet


class Prefetch:
    """
    Class object that allows the prefetching
    of specific fields.
    """

    def __init__(
        self,
        related_name: str,
        to_attr: str,
        queryset: Optional["QuerySet"] = None,
    ) -> None:
        self.related_name = related_name
        self.to_attr = to_attr
        self.queryset = queryset


class PrefetchMixin:
    """
    Query used to perform a prefetch_related into the models and
    subsequent queries.
    """

    def prefetch_related(self, *prefetch: Prefetch) -> "QuerySet":
        """
        Performs a reverse lookup for the foreignkeys. This is different
        from the select_related. Select related performs a follows the SQL foreign relation
        whereas the prefetch_related follows the python relations.
        """
        queryset: "QuerySet" = self._clone()

        if not isinstance(prefetch, (list, tuple)):
            prefetch = cast("List[Prefetch]", [prefetch])  # type: ignore

        if isinstance(prefetch, tuple):
            prefetch = list(prefetch)  # type: ignore

        if any(not isinstance(value, Prefetch) for value in prefetch):
            raise QuerySetError("The prefetch_related must have Prefetch type objects only.")

        prefetch = list(self._prefetch_related) + prefetch  # type: ignore
        queryset._prefetch_related = prefetch
        return queryset
