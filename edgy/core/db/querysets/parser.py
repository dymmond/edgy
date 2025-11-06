from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, cast

import sqlalchemy

from edgy.core.db.datastructures import QueryModelResultCache
from edgy.core.db.querysets.prefetch import Prefetch

from .types import EdgyEmbedTarget, EdgyModel, tables_and_models_type

if TYPE_CHECKING:  # pragma: no cover
    from edgy.core.db.querysets.base import BaseQuerySet


class ResultParser:
    """
    Handles the transformation of database rows into model instances,
    including caching and relationship embedding.
    """

    def __init__(self, queryset: BaseQuerySet | Any) -> None:
        self.queryset = queryset
        self.model_class = queryset.model_class

    async def row_to_model(
        self,
        row: sqlalchemy.Row | Any,
        tables_and_models: tables_and_models_type,
    ) -> tuple[EdgyModel, EdgyEmbedTarget]:
        """
        Parses a single row into a model instance, using the cache.
        (Refactored from _get_or_cache_row)
        """
        is_defer_fields = bool(self.queryset._defer)

        result = await self.queryset._cache.aget_or_cache_many(
            self.model_class,
            [row],
            cache_fn=lambda _row: self.model_class.from_sqla_row(
                _row,
                tables_and_models=tables_and_models,
                select_related=self.queryset._select_related,
                only_fields=self.queryset._only,
                is_defer_fields=is_defer_fields,
                prefetch_related=self.queryset._prefetch_related,
                exclude_secrets=self.queryset._exclude_secrets,
                using_schema=self.queryset.active_schema,
                database=self.queryset.database,
                reference_select=self.queryset._reference_select,
            ),
            transform_fn=self.queryset._embed_parent_in_result,
        )
        return cast(tuple[EdgyModel, EdgyEmbedTarget], result[0])

    async def batch_to_models(
        self,
        batch: Sequence[sqlalchemy.Row],
        tables_and_models: tables_and_models_type,
        prefetch_list: list[Prefetch],
        new_cache: QueryModelResultCache,
    ) -> Sequence[tuple[EdgyModel, EdgyEmbedTarget]]:
        """
        Parses a batch of rows into model instances.
        (This is the parsing half of the original _handle_batch method)
        """
        is_defer_fields = bool(self.queryset._defer)
        qs = self.queryset

        return await new_cache.aget_or_cache_many(
            self.model_class,
            batch,
            cache_fn=lambda row: self.model_class.from_sqla_row(
                row,
                tables_and_models=tables_and_models,
                select_related=qs._select_related,
                only_fields=qs._only,
                is_defer_fields=is_defer_fields,
                prefetch_related=prefetch_list,  # Use the prepared list
                exclude_secrets=qs._exclude_secrets,
                using_schema=qs.active_schema,
                database=qs.database,
                reference_select=qs._reference_select,
            ),
            transform_fn=qs._embed_parent_in_result,
            old_cache=qs._cache,
        )
