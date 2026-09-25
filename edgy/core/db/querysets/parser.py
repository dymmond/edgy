from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Generic, cast

import sqlalchemy

from edgy.core.db.datastructures import QueryModelResultCache

from .types import EdgyEmbedTarget, EdgyModel, tables_and_models_type

if TYPE_CHECKING:  # pragma: no cover
    from edgy.core.db.models.model import Model
    from edgy.core.db.querysets.base import BaseQuerySet
    from edgy.core.db.querysets.queryset import QuerySet


class ResultParser(Generic[EdgyModel, EdgyEmbedTarget]):
    """
    Handles the transformation of database rows into model instances,
    including caching and relationship embedding.
    """

    def __init__(
        self,
        queryset: BaseQuerySet[EdgyModel, EdgyEmbedTarget],
        tables_and_models: tables_and_models_type,
    ) -> None:
        self.queryset = cast("QuerySet[EdgyModel, EdgyEmbedTarget]", queryset)
        self.model_class = cast("type[Model]", queryset.model_class)
        self.tables_and_models = tables_and_models

    async def _row_to_model_uncached(
        self,
        row: sqlalchemy.Row | Any,
    ) -> EdgyModel:
        """
        Parses a single row into a model instance, without using the cache.
        """
        return cast(
            "EdgyModel",
            await self.model_class.from_sqla_row(
                row=row,
                queryset=self.queryset,
                tables_and_models=self.tables_and_models,
                select_related=self.queryset._select_related.union(
                    self.queryset._select_related_embedding
                ),
                reference_select=self.queryset._reference_select,
            ),
        )

    async def row_to_model_uncached(
        self,
        row: sqlalchemy.Row,
    ) -> EdgyModel:
        prepared_prefetches = self.queryset._prepare_prefetches_for_rows(
            rows=[row], tables_and_models=self.tables_and_models
        )
        result = await self._row_to_model_uncached(row)
        if prepared_prefetches:
            await self.queryset._apply_prefetches_self_and_related(
                instance=result,
                tables_and_models=self.tables_and_models,
                mapping=row._mapping,
                prepared_prefetches=prepared_prefetches,
            )
        return result

    async def row_to_model(
        self,
        row: sqlalchemy.Row | Any,
    ) -> tuple[EdgyModel, EdgyEmbedTarget]:
        """
        Parses a single row into a model instance, using the cache.
        (Refactored from _get_or_cache_row)
        """
        prepared_prefetches = self.queryset._prepare_prefetches_for_rows(
            rows=[row], tables_and_models=self.tables_and_models
        )
        result = await self.queryset._cache.aget_or_cache_many(
            self.model_class,
            [row],
            cache_fn=self._row_to_model_uncached,
            transform_fn=lambda pos, instance: self.queryset._embed_parent_in_result(
                cast("EdgyModel", instance),
                mapping=row._mapping,
                tables_and_models=self.tables_and_models,
                prepared_prefetches=prepared_prefetches,
            ),
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
        prepared_prefetches = self.queryset._prepare_prefetches_for_rows(
            rows=batch, tables_and_models=self.tables_and_models
        )
        return await new_cache.aget_or_cache_many(
            self.model_class,
            batch,
            cache_fn=lambda row: self.model_class.from_sqla_row(
                row=row,
                queryset=self.queryset,
                tables_and_models=self.tables_and_models,
                select_related=self.queryset._select_related.union(
                    self.queryset._select_related_embedding
                ),
                reference_select=self.queryset._reference_select,
            ),
            transform_fn=lambda pos, instance: self.queryset._embed_parent_in_result(
                cast("EdgyModel", instance),
                mapping=batch[pos]._mapping,
                tables_and_models=self.tables_and_models,
                prepared_prefetches=prepared_prefetches,
            ),
            old_cache=self.queryset._cache,
        )
