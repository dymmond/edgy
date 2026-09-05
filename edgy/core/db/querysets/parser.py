from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, cast

import sqlalchemy

from edgy.core.db.datastructures import QueryModelResultCache
from edgy.core.db.querysets.prefetch import Prefetch
from edgy.core.db.relationships.utils import crawl_relationship
from edgy.core.utils.db import hash_tablekey
from edgy.exceptions import QuerySetError

from .types import EdgyEmbedTarget, EdgyModel, tables_and_models_type

if TYPE_CHECKING:  # pragma: no cover
    from edgy.core.db.querysets.base import BaseQuerySet
    from edgy.core.db.querysets.queryset import QuerySet


class ResultParser:
    """
    Handles the transformation of database rows into model instances,
    including caching and relationship embedding.
    """

    def __init__(self, queryset: BaseQuerySet, tables_and_models: tables_and_models_type) -> None:
        self.queryset = queryset
        self.model_class = queryset.model_class
        self.tables_and_models = tables_and_models
        self.is_defer_fields = bool(self.queryset._defer)

    def prepare_prefetches_for_rows(
        self,
        rows: Sequence[sqlalchemy.Row],
    ) -> list[Prefetch]:
        """
        Builds the Prefetch objects for a given batch of results.
        This is the *prefetch building* half of the original _handle_batch.

        Args:
            rows: The current batch of SQLAlchemy Row objects.
            tables_and_models: The table/model mapping from the compiler.

        Returns:
            A list of populated Prefetch objects, ready to be executed.

        Raises:
            NotImplementedError: If a prefetch crosses database boundaries.
            QuerySetError: If a prefetch path is invalid (e.g., unidirectional).
        """
        prepared_prefetches: list[Prefetch] = []
        seen_prefetches: set[tuple[None | int, str, str]] = set()

        for prefetch in self.queryset._prefetch_related:
            compare_tuple = (
                id(prefetch.queryset) if prefetch.queryset is not None else None,
                prefetch.related_name,
                prefetch.to_attr,
            )
            if compare_tuple in seen_prefetches:
                continue
            else:
                seen_prefetches.add(compare_tuple)

            crawl_result = crawl_relationship(
                self.model_class, prefetch.related_name, traverse_last=True
            )
            if crawl_result.cross_db_remainder:
                raise NotImplementedError(
                    "Cannot prefetch from other db yet. Maybe in future this feature will be added."
                )
            if crawl_result.reverse_path is False:
                raise QuerySetError(
                    detail=("Creating a reverse path is not possible, unidirectional fields used.")
                )

            prefetch.check_for_collision(self.model_class)
            new_prefetch = Prefetch(related_name=prefetch.related_name, to_attr=prefetch.to_attr)

            prefetch_queryset: QuerySet | None = prefetch.queryset

            clauses = [
                {
                    f"{crawl_result.reverse_path}__{pkcol}": row._mapping[pkcol]
                    for pkcol in crawl_result.model_class.pkcolumns
                }
                for row in rows
            ]
            if prefetch_queryset is None:
                prefetch_queryset = crawl_result.model_class.query.local_or(*clauses)
            else:
                prefetch_queryset = prefetch_queryset.local_or(*clauses)

            if prefetch_queryset.model_class is self.model_class:
                prefetch_queryset = prefetch_queryset.select_related(prefetch.related_name)
                prefetch_queryset.embed_parent = (prefetch.related_name, "")
            else:
                prefetch_queryset = prefetch_queryset.select_related(crawl_result.reverse_path)
            # the assigned queryset has an empty cache
            new_prefetch.queryset = prefetch_queryset
            new_prefetch._baking_model = prefetch_queryset.model_class
            new_prefetch._bake_prefix = f"{hash_tablekey(tablekey=self.tables_and_models[''][0].key, prefix=crawl_result.reverse_path)}_"
            prepared_prefetches.append(new_prefetch)
        return prepared_prefetches

    async def row_to_model_uncached(
        self,
        row: sqlalchemy.Row | Any,
    ) -> EdgyModel:
        """
        Parses a single row into a model instance, without using the cache.
        """
        prepared_prefetches = self.prepare_prefetches_for_rows([row])
        return cast(
            "EdgyModel",
            await self.model_class.from_sqla_row(
                row=row,
                tables_and_models=self.tables_and_models,
                select_related=self.queryset._select_related,
                only_fields=self.queryset._only,
                is_defer_fields=self.is_defer_fields,
                prefetch_related=prepared_prefetches,
                exclude_secrets=self.queryset._exclude_secrets,
                using_schema=self.queryset.active_schema,
                database=self.queryset.database,
                reference_select=self.queryset._reference_select,
            ),
        )

    async def row_to_model(
        self,
        row: sqlalchemy.Row | Any,
    ) -> tuple[EdgyModel, EdgyEmbedTarget]:
        """
        Parses a single row into a model instance, using the cache.
        (Refactored from _get_or_cache_row)
        """
        result = await self.queryset._cache.aget_or_cache_many(
            self.model_class,
            [row],
            cache_fn=self.row_to_model_uncached,
            transform_fn=self.queryset._embed_parent_in_result,
        )
        return cast(tuple[EdgyModel, EdgyEmbedTarget], result[0])

    async def batch_to_models(
        self,
        batch: Sequence[sqlalchemy.Row],
        new_cache: QueryModelResultCache,
    ) -> Sequence[tuple[EdgyModel, EdgyEmbedTarget]]:
        """
        Parses a batch of rows into model instances.
        (This is the parsing half of the original _handle_batch method)
        """
        prepared_prefetches = self.prepare_prefetches_for_rows(batch)
        return await new_cache.aget_or_cache_many(
            self.model_class,
            batch,
            cache_fn=lambda row: self.model_class.from_sqla_row(
                row=row,
                tables_and_models=self.tables_and_models,
                select_related=self.queryset._select_related,
                only_fields=self.queryset._only,
                is_defer_fields=self.is_defer_fields,
                prefetch_related=prepared_prefetches,  # Use the prepared list
                exclude_secrets=self.queryset._exclude_secrets,
                using_schema=self.queryset.active_schema,
                database=self.queryset.database,
                reference_select=self.queryset._reference_select,
            ),
            transform_fn=self.queryset._embed_parent_in_result,
            old_cache=self.queryset._cache,
        )
