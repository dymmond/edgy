from __future__ import annotations

import warnings
from collections.abc import AsyncGenerator, Sequence
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any, cast

import sqlalchemy

from edgy.core.db.context_vars import CURRENT_INSTANCE
from edgy.core.db.datastructures import QueryModelResultCache
from edgy.core.db.querysets.prefetch import Prefetch, check_prefetch_collision
from edgy.core.db.relationships.utils import crawl_relationship
from edgy.core.utils.db import check_db_connection, hash_tablekey
from edgy.exceptions import MultipleObjectsReturned, ObjectNotFound, QuerySetError

from .types import EdgyEmbedTarget, EdgyModel

if TYPE_CHECKING:  # pragma: no cover
    from edgy.core.db.querysets.base import BaseQuerySet
    from edgy.core.db.querysets.compiler import QueryCompiler
    from edgy.core.db.querysets.parser import ResultParser
    from edgy.core.db.querysets.queryset import QuerySet

    from .types import tables_and_models_type


_current_row_holder: ContextVar[list[sqlalchemy.Row | None] | None] = ContextVar(
    "_current_row_holder", default=None
)


def get_current_row() -> sqlalchemy.Row | None:
    """Get async safe the current row when in _execute_iterate"""
    row_holder = _current_row_holder.get()
    if not row_holder:
        return None
    return row_holder[0]


class QueryExecutor:
    """
    Runs compiled queries against the database, manages iteration,
    and coordinates prefetching, parsing, and deleting.
    """

    def __init__(
        self,
        queryset: BaseQuerySet,
        compiler: QueryCompiler,
        parser: ResultParser,
    ):
        """
        Initializes the QueryExecutor.

        Args:
            queryset: The BaseQuerySet instance holding the query state.
            compiler: The QueryCompiler to be used for WHERE clauses (e.g., in deletes).
            parser: The ResultParser to be used for turning rows into models.
        """
        self.queryset = queryset
        self.compiler = compiler
        self.parser = parser
        self.database = queryset.database
        self.model_class = queryset.model_class

    async def _process_and_yield_batch(
        self,
        batch: Sequence[sqlalchemy.Row],
        tables_and_models: tables_and_models_type,
        new_cache: QueryModelResultCache,
    ) -> AsyncGenerator[tuple[tuple[EdgyModel, EdgyEmbedTarget], sqlalchemy.Row], None]:
        """
        Processes a single batch of rows.

        This helper method prepares prefetches, parses rows into models,
        and yields the (result_tuple, row) for the iterator.

        Args:
            batch: A list of raw SQLAlchemy Row objects.
            tables_and_models: The table/model mapping from the compiler.
            new_cache: The result cache to populate.

        Yields:
            A tuple containing:
                - (result_tuple): The (raw_model, embed_target) tuple.
                - (row): The raw SQLAlchemy Row.
        """
        prefetches = await self._prepare_prefetches_for_batch(batch, tables_and_models)
        results: Sequence[tuple[EdgyModel, EdgyEmbedTarget]] = await self.parser.batch_to_models(
            batch, tables_and_models, prefetches, new_cache
        )

        for row_num, result_tuple in enumerate(results):
            yield result_tuple, batch[row_num]

    async def iterate(self, fetch_all_at_once: bool = False) -> AsyncGenerator[EdgyModel, None]:
        """
        Executes the query and iterates over results, yielding model instances.

        This method orchestrates the query execution, handling either
        fetching all results at once or iterating in batches.

        Args:
            fetch_all_at_once: If True, fetches all rows from the database in
                a single query. If False, uses a batched iterator.

        Yields:
            EdgyModel: A populated model instance for each row.
        """
        qs = self.queryset
        if qs._cache_fetch_all:
            for result in cast(
                Sequence[tuple[EdgyModel, Any]],
                qs._cache.get_category(self.model_class).values(),
            ):
                yield result[1]
            return

        if qs.embed_parent:
            qs = qs.distinct()  # type: ignore

        expression, tables_and_models = await qs.as_select_with_tables()

        if not fetch_all_at_once and bool(self.database.force_rollback):
            warnings.warn(
                'Using queryset iterations with "Database"-level force_rollback set is risky. '
                "Deadlocks can occur because only one connection is used.",
                UserWarning,
                stacklevel=3,
            )
            if qs._prefetch_related:
                fetch_all_at_once = True

        counter = 0
        last_element: tuple[EdgyModel, Any] | None = None
        check_db_connection(self.database, stacklevel=4)
        current_row: list[sqlalchemy.Row | None] = [None]
        token = _current_row_holder.set(current_row)

        try:
            if fetch_all_at_once:
                new_cache = QueryModelResultCache(qs._cache.attrs)
                async with self.database as database:
                    batch = cast(Sequence[sqlalchemy.Row], await database.fetch_all(expression))

                # Use the new helper to process the single, large batch
                async for result, row in self._process_and_yield_batch(
                    batch, tables_and_models, new_cache
                ):
                    if counter == 0:
                        qs._cache_first = result
                    last_element = result
                    counter += 1
                    current_row[0] = row
                    yield result[1]

                qs._cache_fetch_all = True
                qs._cache = new_cache
            else:
                batch_num: int = 0
                new_cache = QueryModelResultCache(qs._cache.attrs)
                async with self.database as database:
                    async for batch in cast(
                        AsyncGenerator[Sequence[sqlalchemy.Row], None],
                        database.batched_iterate(expression, batch_size=qs._batch_size),
                    ):
                        new_cache.clear()
                        qs._cache_fetch_all = False

                        # Use the new helper to process each batch
                        async for result, row in self._process_and_yield_batch(
                            batch, tables_and_models, new_cache
                        ):
                            if counter == 0:
                                qs._cache_first = result
                            last_element = result
                            counter += 1
                            current_row[0] = row
                            yield result[1]  # Yield the embed target
                        batch_num += 1

                if batch_num <= 1:
                    qs._cache = new_cache
                    qs._cache_fetch_all = True
        finally:
            _current_row_holder.reset(token)

        qs._cache_count = counter
        qs._cache_last = last_element

    async def get_one(self) -> tuple[EdgyModel, EdgyEmbedTarget]:
        """
        Fetches a single unique record from the database.
        This is the refactored _get_raw (when no kwargs are present).

        Returns:
            A tuple of (raw_model, embed_target).

        Raises:
            ObjectNotFound: If no record is found.
            MultipleObjectsReturned: If more than one record is found.
        """
        expression, tables_and_models = await self.queryset.as_select_with_tables()
        check_db_connection(self.database, stacklevel=4)

        async with self.database as database:
            rows = await database.fetch_all(expression.limit(2))

        if not rows:
            self.queryset._cache_count = 0
            raise ObjectNotFound()
        if len(rows) > 1:
            raise MultipleObjectsReturned()

        self.queryset._cache_count = 1

        result: tuple[EdgyModel, EdgyEmbedTarget] = await self.parser.row_to_model(
            rows[0], tables_and_models
        )

        # Update cache attributes
        self.queryset._cache_first = result
        self.queryset._cache_last = result
        return result

    async def _prepare_prefetches_for_batch(
        self,
        batch: Sequence[sqlalchemy.Row],
        tables_and_models: tables_and_models_type,
    ) -> list[Prefetch]:
        """
        Builds the Prefetch objects for a given batch of results.
        This is the *prefetch building* half of the original _handle_batch.

        Args:
            batch: The current batch of SQLAlchemy Row objects.
            tables_and_models: The table/model mapping from the compiler.

        Returns:
            A list of populated Prefetch objects, ready to be executed.

        Raises:
            NotImplementedError: If a prefetch crosses database boundaries.
            QuerySetError: If a prefetch path is invalid (e.g., unidirectional).
        """
        prepared_prefetches: list[Prefetch] = []
        qs = self.queryset

        for prefetch in qs._prefetch_related:
            check_prefetch_collision(self.model_class, prefetch)  # type: ignore

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

            prefetch_queryset: QuerySet | None = prefetch.queryset

            clauses = [
                {
                    f"{crawl_result.reverse_path}__{pkcol}": row._mapping[pkcol]
                    for pkcol in self.model_class.pkcolumns
                }
                for row in batch
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

            new_prefetch = Prefetch(
                related_name=prefetch.related_name,
                to_attr=prefetch.to_attr,
                queryset=prefetch_queryset,
            )
            new_prefetch._bake_prefix = f"{hash_tablekey(tablekey=tables_and_models[''][0].key, prefix=crawl_result.reverse_path)}_"
            new_prefetch._is_finished = True
            prepared_prefetches.append(new_prefetch)

        return prepared_prefetches

    async def delete(
        self, use_models: bool = False, remove_referenced_call: str | bool = False
    ) -> int:
        """
        Executes a delete operation.

        This method coordinates the deletion, deciding whether to perform a
        fast, raw SQL delete or a slower, model-based delete (which runs hooks).

        Args:
            use_models: If True, deletion is performed by iterating and
                deleting individual model instances.
            remove_referenced_call: Specifies how to handle referenced objects
                during deletion (passed to model.raw_delete).

        Returns:
            The number of rows deleted.
        """
        if (
            self.model_class.__require_model_based_deletion__
            or self.model_class.meta.post_delete_fields
        ):
            use_models = True

        if use_models:
            row_count = await self._model_based_delete(
                remove_referenced_call=remove_referenced_call
            )
        else:
            expression = self.queryset.table.delete()
            expression = expression.where(await self.compiler.build_where_clause())

            check_db_connection(self.database)
            async with self.database as database:
                row_count = cast(int, await database.execute(expression))

        # clear cache before executing post_delete.
        self.queryset._clear_cache()
        return row_count

    async def _model_based_delete(self, remove_referenced_call: str | bool) -> int:
        """
        Performs a model-based deletion by iterating over models in batches.

        This method ensures that each model's `raw_delete` method is called,
        allowing all pre/post_delete hooks and signal handlers to run.

        Args:
            remove_referenced_call: Passed to each model's `raw_delete` method.

        Returns:
            The total number of models deleted.
        """
        from edgy.core.db.querysets.compiler import QueryCompiler
        from edgy.core.db.querysets.parser import ResultParser

        queryset = (
            self.queryset.limit(self.queryset._batch_size)
            if not self.queryset._cache_fetch_all
            else self.queryset
        )
        queryset.embed_parent = None
        row_count = 0

        compiler = QueryCompiler(queryset)  # type: ignore
        parser = ResultParser(queryset)

        # Instantiate the QueryExecutor recursively for the new queryset
        executor = QueryExecutor(queryset, compiler, parser)  # type: ignore

        # Uuse the new executor's iterate method
        models = [model async for model in executor.iterate(fetch_all_at_once=True)]  # type: ignore

        token = CURRENT_INSTANCE.set(self.queryset)
        try:
            while models:
                for model in models:
                    await model.raw_delete(
                        skip_post_delete_hooks=False, remove_referenced_call=remove_referenced_call
                    )
                    row_count += 1

                # clear cache and fetch new batch
                queryset._clear_cache(keep_result_cache=False)
                models = [model async for model in executor.iterate(fetch_all_at_once=True)]  # type: ignore
        finally:
            CURRENT_INSTANCE.reset(token)
        return row_count
