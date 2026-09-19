from __future__ import annotations

import asyncio
import warnings
from collections import defaultdict
from collections.abc import Hashable, Iterable, Mapping
from functools import cached_property
from inspect import isclass
from typing import TYPE_CHECKING, Any, cast

from edgy.core.db.querysets.types import tables_and_models_type
from edgy.core.db.relationships.utils import crawl_relationship
from edgy.exceptions import QuerySetError

if TYPE_CHECKING:
    from edgy.core.db.models.types import BaseModelType
    from edgy.core.db.relationships.utils import RelationshipCrawlResult

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
        *args: Any,
        related_name: str,
        to_attr: str,
        queryset: QuerySet | None = None,
        from_anchor: str | None = None,
    ) -> None:
        """
        Initializes a Prefetch object.

        Kwargs:
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
            from_anchor (str | None): The path to the start of related_name and to_attr. Can be a submodel.
                                      Leave empty to use the default, the current model.
        """
        if args:
            warnings.warn("`Prefetch` is now keyword-only.", DeprecationWarning, stacklevel=2)
            self.related_name = args[0]
            to_attr = args[1]
        else:
            self.related_name = related_name
        self.queryset: QuerySet | None = queryset
        self.from_anchor = from_anchor or ""
        if to_attr.startswith("+"):
            to_attr = f"{from_anchor}__{to_attr[1:]}" if from_anchor else to_attr
        self.to_attr: str = to_attr
        if not self.to_attr:
            raise ValueError("`to_attr` cannot be empty.")
        if self.to_attr.startswith("+"):
            raise ValueError("`to_attr` cannot start with multiple `+`.")
        # Internal flag to indicate if the baking process of _bake_without_mapping path has been completed.
        self._baked = False
        # Internal flag if clauses are set
        self._bake_without_mapping = False

    @cached_property
    def _baking_finished(self) -> asyncio.Event:
        """
        Wait until baking is finished.

        Placeholder which raises when not initialized.
        """
        raise QuerySetError("`_baking_finished` not set.")

    @cached_property
    def _anchor(self) -> RelationshipCrawlResult:
        """
        Maps back to anchor crawl result.

        Placeholder which raises when not initialized.
        """
        raise QuerySetError("`_anchor` not set.")

    @cached_property
    def _reverse_path_to_anchor(self) -> str:
        """
        Maps back to anchor model.

        Placeholder which raises when not initialized.
        """
        raise QuerySetError("`_reverse_path_to_anchor` not set.")

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
        attr_name = self.to_attr.rsplit("__", 1)[-1]
        # Check for collision with existing attributes, model fields, or model managers.
        if (
            hasattr(model, attr_name)
            or attr_name in model.meta.fields
            or attr_name in model.meta.managers
        ):
            if not isclass(model):
                model = cast("type[BaseModelType]", type(model))
            raise QuerySetError(
                f"Conflicting attribute to_attr='{attr_name}' for related_name=`{self.related_name}` "
                f"on {model.__name__}"
            )

    def _generate_select_related_pathes(self, queryset: QuerySet) -> Iterable[str]:
        """Generate pathes for select related."""
        pathes: set[str] = set()
        anchor_forward_path = self.from_anchor.rsplit("__", 1)[0]

        if anchor_forward_path:
            crawl_result = crawl_relationship(
                queryset.model_class,
                anchor_forward_path,
                model_database=queryset.database,
                embed_parent=queryset.embed_parent_filters,
                traverse_last=True,
                allow_crossing_db=False,
            )
            # for cross db requests this is okay
            if crawl_result.field_name and not crawl_result.cross_db_remainder:
                raise ValueError(
                    f"Should not find a field name: `{crawl_result.field_name}` on `{crawl_result.model_class}`, "
                    "should be a path to a model."
                )
            if crawl_result.forward_path:
                pathes.add(crawl_result.forward_path)
        if "__" in self.to_attr:
            crawl_result = crawl_relationship(
                queryset.model_class,
                self.to_attr,
                model_database=queryset.database,
                embed_parent=queryset.embed_parent_filters,
                allow_crossing_db=True,
            )
            # for cross db requests this is okay
            if crawl_result.field_name and not crawl_result.cross_db_remainder:
                pathes.add(crawl_result.forward_path)
        return pathes

    def _set_clauses_by_mappings(
        self,
        *,
        mappings: Iterable[Mapping],
        tables_and_models: tables_and_models_type | None = None,
    ) -> None:
        assert self.queryset is not None
        row_prefix = (
            f"{tables_and_models[self._anchor.forward_path][0].name}_"
            if self._anchor.forward_path and tables_and_models is not None
            else ""
        )
        clauses = [
            {
                f"{self._reverse_path_to_anchor}__{pkcol}": mapping[f"{row_prefix}{pkcol}"]
                for pkcol in self._anchor.model_class.pkcolumns
            }
            for mapping in mappings
        ]
        self.queryset = self.queryset.local_or(*clauses)
        # can bake without extra_mapping
        self._bake_without_mapping = True

    async def _init_bake(self, mapping: Mapping | None = None) -> None:
        """
        (Internal method) Initializes the baking process for prefetching related objects.

        This asynchronous method is responsible for executing the internal
        `queryset` (if it exists and the process is ready) and populating
        the `_baked_results` dictionary. It iterates through the results
        from the queryset, creates a unique `model_key` for each related
        instance based on the `model_class` and `_bake_prefix`, and then
        appends the result to the corresponding list in `_baked_results`.
        This effectively groups related objects by their parent model's key
        """
        from .executor import QueryExecutor

        anchor_model = self._anchor.model_class
        qs = self.queryset
        assert qs is not None, "`queryset` not initialized"
        assert self._bake_without_mapping == (mapping is None), "Wrong baking path used"
        if mapping is None:
            # only true if clauses are set
            if not self._bake_without_mapping:
                return
            # If already baking check event.
            if self._baked:
                await self._baking_finished.wait()
                return
            self._baked = True
        else:
            clauses = {
                f"{self._reverse_path_to_anchor}__{pkcol}": mapping[pkcol]
                for pkcol in anchor_model.pkcolumns
            }
            qs = qs.filter(**clauses)
        # Execute the queryset and asynchronously iterate over the results.
        # The `True` argument for `_execute_iterate` ensures all results are
        # fetched at once for processing.
        executor = QueryExecutor(qs)
        result_dict = defaultdict(list)
        first = True
        async for _, result in executor.iterate(True):
            # now this is initialized
            if first:
                bake_prefix = (
                    f"{executor.parser.tables_and_models[self._reverse_path_to_anchor][0].name}_"
                )
                first = False
            # Create a unique model key from the current SQLAlchemy row using the
            # specified bake prefix. This key links the prefetched item back to
            # its parent model instance.
            model_key = anchor_model.create_model_key_from_raw_mapping(
                mapping=executor._current_row._mapping, prefix=bake_prefix
            )
            # Append the prefetched result to the list associated with its model key.
            result_dict[model_key].append(result)
        self._baked_results.update(result_dict)
        if mapping is None:
            self._baking_finished.set()


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
