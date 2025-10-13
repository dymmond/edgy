from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any

from edgy.exceptions import QuerySetError

if TYPE_CHECKING:
    from edgy import Model, QuerySet
    from edgy.core.db.models.types import BaseModelType


class Prefetch:
    """
    Class object that allows the prefetching of specific fields.

    This class defines a prefetch operation, specifying a related field to load
    and the attribute name on the main model where the prefetched results will
    be attached. It also manages the internal state for the baking process,
    where results are fetched and prepared for attachment.
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
            related_name (str): The name of the related field (e.g., a reverse
                                 foreign key relation or a many-to-many relation)
                                 to prefetch. This corresponds to the name of the
                                 relationship as defined in the model.
            to_attr (str): The attribute name on the main model instances to which
                           the prefetched related objects will be attached. This
                           should be a unique name that does not conflict with
                           existing model attributes or fields.
            queryset (QuerySet | None): An optional `QuerySet` instance to use for
                                         fetching the related objects. If not
                                         provided, Edgy will construct a default
                                         queryset for the related model. This allows
                                         for custom filtering or ordering of the
                                         prefetched data.
        """
        self.related_name = related_name
        self.to_attr = to_attr
        self.queryset: QuerySet | None = queryset
        # Internal flag to indicate if the prefetching process has finished.
        self._is_finished = False
        # Internal prefix used during the baking process for creating model keys.
        self._bake_prefix: str = ""
        # A defaultdict to store the baked results, mapping model keys to lists of
        # related instances.
        self._baked_results: dict[tuple[str, ...], list[Any]] = defaultdict(list)
        # Internal flag to indicate if the baking process has been completed.
        self._baked = False

    async def init_bake(self, model_class: type[Model]) -> None:
        """
        Initializes the baking process for prefetching related objects.

        This asynchronous method is responsible for executing the internal
        `queryset` (if it exists and the process is ready) and populating
        the `_baked_results` dictionary. It iterates through the results
        from the queryset, creates a unique `model_key` for each related
        instance based on the `model_class` and `_bake_prefix`, and then
        appends the result to the corresponding list in `_baked_results`.
        This effectively groups related objects by their parent model's key.

        Args:
            model_class (type[Model]): The main model class to which the prefetched
                                        results will eventually be attached. This
                                        is used to create the model keys for grouping.
        """
        # If already baked, not finished, or no queryset, do not proceed.
        if self._baked or not self._is_finished or self.queryset is None:
            return
        self._baked = True
        # Execute the queryset and asynchronously iterate over the results.
        # The `True` argument for `_execute_iterate` ensures all results are
        # fetched at once for processing.
        async for result in self.queryset._execute_iterate(True):
            # Create a unique model key from the current SQLAlchemy row using the
            # specified bake prefix. This key links the prefetched item back to
            # its parent model instance.
            model_key = model_class.create_model_key_from_sqla_row(
                self.queryset._current_row, row_prefix=self._bake_prefix
            )
            # Append the prefetched result to the list associated with its model key.
            self._baked_results[model_key].append(result)


def check_prefetch_collision(model: BaseModelType, related: Prefetch) -> Prefetch:
    """
    Checks for potential attribute name collisions when prefetching.

    This function ensures that the `to_attr` specified in a `Prefetch` object
    does not conflict with any existing attributes, fields (database columns),
    or managers defined on the target `model`. A collision could lead to
    unexpected behavior or overwriting of crucial model components.

    Args:
        model (BaseModelType): The model class instance to which the prefetched
                               results will be attached. This is the "parent"
                               model in the prefetch relationship.
        related (Prefetch): The `Prefetch` object containing the `to_attr`
                            that needs to be checked for collisions.

    Returns:
        Prefetch: The `Prefetch` object itself if no collision is detected,
                  allowing for method chaining or direct use.

    Raises:
        QuerySetError: If the `to_attr` from the `Prefetch` object conflicts
                       with an existing attribute, field, or manager on the
                       `model`. The error message specifies the conflicting
                       attribute and the model class.
    """
    # Check for collision with existing attributes, model fields, or model managers.
    if (
        hasattr(model, related.to_attr)
        or related.to_attr in model.meta.fields
        or related.to_attr in model.meta.managers
    ):
        raise QuerySetError(
            f"Conflicting attribute to_attr='{related.related_name}' with "
            f"'{related.to_attr}' in {model.__class__.__name__}"
        )
    return related


class PrefetchMixin:
    """
    Mixin class providing methods for performing `prefetch_related` operations
    on a QuerySet.

    This mixin distinguishes between `select_related` (which performs SQL joins)
    and `prefetch_related` (which performs separate lookups and Python-side
    object mapping). It allows users to specify relationships that should be
    eagerly loaded into separate attributes of the main model instances.
    """

    def prefetch_related(self, *prefetch: Prefetch) -> QuerySet:
        """
        Performs a reverse lookup for foreign keys and other relationships,
        populating results onto the main model instances.

        This method is distinct from `select_related` in that `select_related`
        performs a SQL JOIN to fetch related data in the same query, whereas
        `prefetch_related` executes separate queries for each relationship
        and then joins the results in Python. This is particularly useful for
        many-to-many relationships or reverse foreign key lookups, or when
        preloading related objects for a large set of parent objects.

        Args:
            *prefetch (Prefetch): One or more `Prefetch` objects, each defining
                                   a relationship to prefetch, including the
                                   `related_name` and the `to_attr` where results
                                   will be stored. An optional custom `QuerySet`
                                   can also be provided within the `Prefetch` object.

        Returns:
            QuerySet: A new `QuerySet` instance with the specified prefetch
                      relationships configured. This new QuerySet can then be
                      further filtered, ordered, or executed.

        Raises:
            QuerySetError: If any argument passed to `prefetch` is not an
                           instance of the `Prefetch` class.
        """
        queryset: QuerySet = self._clone()

        # Validate that all provided arguments are instances of Prefetch.
        if any(not isinstance(value, Prefetch) for value in prefetch):
            raise QuerySetError("The prefetch_related must have Prefetch type objects only.")

        # Append the new prefetch objects to the queryset's internal list.
        queryset._prefetch_related = [*self._prefetch_related, *prefetch]
        return queryset
