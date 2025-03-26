from collections import defaultdict
from typing import TYPE_CHECKING, Any, Optional

from edgy.exceptions import QuerySetError

if TYPE_CHECKING:
    from edgy import Model, QuerySet
    from edgy.core.db.models.types import BaseModelType


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
        self.queryset: Optional[QuerySet] = queryset
        self._is_finished = False
        self._bake_prefix: str = ""
        self._baked_results: dict[tuple[str, ...], list[Any]] = defaultdict(list)
        self._baked = False

    async def init_bake(self, model_class: type["Model"]) -> None:
        if self._baked or not self._is_finished or self.queryset is None:
            return
        self._baked = True
        # we want all at once and async iterate
        async for result in self.queryset._execute_iterate(True):
            # a bit hacky but we need the current row
            model_key = model_class.create_model_key_from_sqla_row(
                self.queryset._current_row, row_prefix=self._bake_prefix
            )
            self._baked_results[model_key].append(result)


def check_prefetch_collision(model: "BaseModelType", related: Prefetch) -> Prefetch:
    if (
        hasattr(model, related.to_attr)
        or related.to_attr in model.meta.fields
        or related.to_attr in model.meta.managers
    ):
        raise QuerySetError(
            f"Conflicting attribute to_attr='{related.related_name}' with '{related.to_attr}' in {model.__class__.__name__}"
        )
    return related


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
        queryset: QuerySet = self._clone()

        if any(not isinstance(value, Prefetch) for value in prefetch):
            raise QuerySetError("The prefetch_related must have Prefetch type objects only.")

        queryset._prefetch_related = [*self._prefetch_related, *prefetch]
        return queryset
