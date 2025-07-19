from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any

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
        queryset: QuerySet | None = None,
    ) -> None:
        """
        Initializes a Prefetch object.

        Args:
            related_name (str): The name of the related field to prefetch.
            to_attr (str): The attribute name on the main model to which the prefetched
                           results will be attached.
            queryset (QuerySet | None): An optional QuerySet to use for prefetching.
                                         If not provided, the default queryset for the
                                         related model will be used.
        """
        self.related_name = related_name
        self.to_attr = to_attr
        self.queryset: QuerySet | None = queryset
        self._is_finished = False
        self._bake_prefix: str = ""
        self._baked_results: dict[tuple[str, ...], list[Any]] = defaultdict(list)
        self._baked = False

    async def init_bake(self, model_class: type[Model]) -> None:
        """
        Initializes the baking process for prefetching.

        This method populates `_baked_results` by executing the `queryset`
        and mapping the results back to the appropriate model instances
        using `model_key`.

        Args:
            model_class (type[Model]): The model class associated with the prefetch operation.
        """
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


def check_prefetch_collision(model: BaseModelType, related: Prefetch) -> Prefetch:
    """
    Checks for potential attribute name collisions when prefetching.

    Ensures that the `to_attr` specified in a Prefetch object does not conflict
    with existing attributes, fields, or managers on the target model.

    Args:
        model (BaseModelType): The model class to which the prefetched results will be attached.
        related (Prefetch): The Prefetch object to check.

    Returns:
        Prefetch: The Prefetch object if no collision is detected.

    Raises:
        QuerySetError: If `to_attr` conflicts with an existing attribute, field, or manager.
    """
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

    def prefetch_related(self, *prefetch: Prefetch) -> QuerySet:
        """
        Performs a reverse lookup for the foreignkeys. This is different
        from the select_related. Select related performs a follows the SQL foreign relation
        whereas the prefetch_related follows the python relations.

        Args:
            *prefetch (Prefetch): One or more Prefetch objects defining the relationships
                                   to prefetch.

        Returns:
            QuerySet: A new QuerySet with the specified prefetch relationships configured.

        Raises:
            QuerySetError: If any argument in `prefetch` is not an instance of `Prefetch`.
        """
        queryset: QuerySet = self._clone()

        if any(not isinstance(value, Prefetch) for value in prefetch):
            raise QuerySetError("The prefetch_related must have Prefetch type objects only.")

        queryset._prefetch_related = [*self._prefetch_related, *prefetch]
        return queryset
