from __future__ import annotations

import warnings
from collections import defaultdict
from collections.abc import Hashable
from functools import cached_property
from inspect import isclass
from typing import TYPE_CHECKING, Any, cast

from edgy.exceptions import QuerySetError

if TYPE_CHECKING:
    from edgy.core.db.models.model import Model
    from edgy.core.db.models.types import BaseModelType

    from .queryset import QuerySet


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
        # Internal flag to indicate if the baking process has been completed.
        self._baked = False

    @cached_property
    def _bake_prefix(self) -> str:
        """
        Maps back to target model.

        Placeholder which raises when not initialized.
        """
        raise QuerySetError("`_bake_prefix` not set.")

    @cached_property
    def _target_model(self) -> type[Model]:
        """
        Holds origin model (source model, where prefetches are attached).

        Placeholder which raises when not initialized.
        """
        raise QuerySetError("`_target_model` not set.")

    @cached_property
    def _baked_results(self) -> dict[tuple[Hashable, ...], list[Any]]:
        """
        Persisted dict to store the baked results, mapping model keys to lists of
        related instances.

        Placeholder which raises when not initialized.
        """
        raise QuerySetError("`_baked_results` not set.")

    def check_for_collision(self, model: type[BaseModelType] | BaseModelType) -> None:
        """
        Checks for potential attribute name collisions when prefetching.

        This function ensures that the `to_attr` specified in a `Prefetch` object
        does not conflict with any existing attributes, fields (database columns),
        or managers defined on the target `model`. A collision could lead to
        unexpected behavior or overwriting of crucial model components.

        Args:
            model (type[BaseModelType] | BaseModelType):
                The model class to which the prefetched
                results will be attached. This is the "parent"
                model in the prefetch relationship.

        Raises:
            QuerySetError: If the `to_attr` from the `Prefetch` object conflicts
                        with an existing attribute, field, or manager on the
                        `model`. The error message specifies the conflicting
                        attribute and the model class.
        """
        # Check for collision with existing attributes, model fields, or model managers.
        if (
            hasattr(model, self.to_attr)
            or self.to_attr in model.meta.fields
            or self.to_attr in model.meta.managers
        ):
            if not isclass(model):
                model = cast("type[BaseModelType]", type(model))
            raise QuerySetError(
                f"Conflicting attribute to_attr='{self.related_name}' with "
                f"'{self.to_attr}' in {model.__name__}"
            )

    async def init_bake(self) -> None:
        """
        Initializes the baking process for prefetching related objects.

        This asynchronous method is responsible for executing the internal
        `queryset` (if it exists and the process is ready) and populating
        the `_baked_results` dictionary. It iterates through the results
        from the queryset, creates a unique `model_key` for each related
        instance based on the `model_class` and `_bake_prefix`, and then
        appends the result to the corresponding list in `_baked_results`.
        This effectively groups related objects by their parent model's key
        """
        from .executor import QueryExecutor

        # If already baked or without baking model do not proceed.
        if self._baked:
            return
        qs = self.queryset
        assert qs is not None
        self._baked = True
        # Execute the queryset and asynchronously iterate over the results.
        # The `True` argument for `_execute_iterate` ensures all results are
        # fetched at once for processing.
        executor = QueryExecutor(qs)
        result_dict = defaultdict(list)
        async for _, result in executor.iterate(True):
            # Create a unique model key from the current SQLAlchemy row using the
            # specified bake prefix. This key links the prefetched item back to
            # its parent model instance.
            model_key = self._target_model.create_model_key_from_sqla_row(
                row=executor._current_row, row_prefix=self._bake_prefix
            )
            # Append the prefetched result to the list associated with its model key.
            result_dict[model_key].append(result)
        self._baked_results.update(result_dict)


def check_prefetch_collision(
    model: type[BaseModelType] | BaseModelType, related: Prefetch
) -> Prefetch:
    """
    Checks for potential attribute name collisions when prefetching.

    This function ensures that the `to_attr` specified in a `Prefetch` object
    does not conflict with any existing attributes, fields (database columns),
    or managers defined on the target `model`. A collision could lead to
    unexpected behavior or overwriting of crucial model components.

    Args:
        model (type[BaseModelType] | BaseModelType): The model class to which the prefetched
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
    warnings.warn(
        "This method is deprecated. Use `prefetch.check_for_collision` instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    related.check_for_collision(model)
    return related
