from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Mapping, Sequence
from inspect import isawaitable
from typing import TYPE_CHECKING, Any, Generic, cast, overload

import sqlalchemy

from edgy.core.db.context_vars import MODEL_GETATTR_BEHAVIOR
from edgy.core.db.querysets.prefetch import Prefetch
from edgy.core.db.querysets.types import EdgyEmbedTarget, EdgyModel, tables_and_models_type
from edgy.core.db.relationships.utils import crawl_relationship
from edgy.core.utils.concurrency import run_concurrently
from edgy.exceptions import QuerySetError

if TYPE_CHECKING:  # pragma: no cover
    from edgy import Model
    from edgy.core.db.models.types import BaseModelType
    from edgy.core.db.querysets.prefetch import Prefetch
    from edgy.core.db.querysets.queryset import QuerySet


class EmbeddingMixin(Generic[EdgyModel, EdgyEmbedTarget]):
    """
    Mixin class providing methods for performing embedding operations
    on a QuerySet like `prefetch_related` and `_embed_parent_in_result`.
    """

    async def _apply_prefetches_list(
        self,
        *,
        instance: BaseModelType,
        prefetches: Sequence[Prefetch],
        mapping: Mapping,
        prefix: str = "",
        tables_and_models: tables_and_models_type | None = None,
    ) -> None:
        self_queryset = cast("QuerySet[EdgyModel, EdgyEmbedTarget]", self)
        assert not prefix or tables_and_models
        # tables can be alias
        row_prefix = (
            f"{tables_and_models[prefix][0].name}_" if prefix and tables_and_models else ""
        )
        model_key = self_queryset.model_class.create_model_key_from_raw_mapping(
            mapping=mapping, prefix=row_prefix
        )
        await run_concurrently(
            [prefetch._init_bake() for prefetch in prefetches],
            limit=1 if getattr(self_queryset.database, "force_rollback", False) else None,
        )
        for related in prefetches:
            assert (prefix or "") == related._forward_path
            # Check for conflicting names early to prevent unexpected overwrites.
            related.check_for_collision(model=instance)
            # Ensure it is in the baked results.
            related._baked_results.setdefault(model_key, [])
            object.__setattr__(instance, related.to_attr, list(related._baked_results[model_key]))

    async def _apply_prefetches_self_and_select_related(
        self,
        *,
        instance: EdgyModel,
        prefetches_dict: dict[str, list[Prefetch]],
        mapping: Mapping,
        tables_and_models: tables_and_models_type | None,
        seen: set[str],
    ) -> None:
        self_queryset = cast("QuerySet[EdgyModel, EdgyEmbedTarget]", self)
        prefix = ""
        token = MODEL_GETATTR_BEHAVIOR.set("passdown")
        try:
            if prefetches_list := prefetches_dict.get(""):
                await self._apply_prefetches_list(
                    instance=instance,
                    prefix=prefix,
                    mapping=mapping,
                    tables_and_models=tables_and_models,
                    prefetches=prefetches_list,
                )
            for path in self_queryset._select_related:
                new_result: BaseModelType = instance
                for part in path.split("__"):
                    prefix = f"{prefix}__{part}" if prefix else part
                    new_result = cast("BaseModelType", getattr(new_result, part))
                    if prefix in seen:
                        continue
                    seen.add(prefix)
                    if prefetches_list := prefetches_dict.get(prefix):
                        await self._apply_prefetches_list(
                            instance=new_result,
                            prefix=prefix,
                            mapping=mapping,
                            tables_and_models=tables_and_models,
                            prefetches=prefetches_list,
                        )
        finally:
            MODEL_GETATTR_BEHAVIOR.reset(token)

    @overload
    async def _embed_parent_in_result(
        self,
        result: None,
        mapping: Mapping | None = None,
        prefetches_dict: dict[str, list[Prefetch]] | None = None,
        tables_and_models: tables_and_models_type | None = None,
    ) -> tuple[None, None]: ...
    @overload
    async def _embed_parent_in_result(
        self,
        result: EdgyModel | Awaitable[EdgyModel],
        mapping: Mapping | None = None,
        prefetches_dict: dict[str, list[Prefetch]] | None = None,
        tables_and_models: tables_and_models_type | None = None,
    ) -> tuple[EdgyModel, EdgyEmbedTarget]: ...
    async def _embed_parent_in_result(
        self,
        result: EdgyModel | Awaitable[EdgyModel] | None,
        mapping: Mapping | None = None,
        prefetches_dict: dict[str, list[Prefetch]] | None = None,
        tables_and_models: tables_and_models_type | None = None,
    ) -> tuple[EdgyModel, EdgyEmbedTarget] | tuple[None, None]:
        """
        This is a result transformation, called by the Parser.
        """
        self_queryset = cast("QuerySet[EdgyModel, EdgyEmbedTarget]", self)
        if isawaitable(result):
            result = await result
        if result is None:
            return None, None
        seen_prefixes: set[str] = set()
        if mapping is not None and prefetches_dict:
            await self._apply_prefetches_self_and_select_related(
                instance=result,
                prefetches_dict=prefetches_dict,
                mapping=mapping,
                tables_and_models=tables_and_models,
                seen=seen_prefixes,
            )
        if not self_queryset.embed_parent:
            return result, cast("EdgyEmbedTarget", result)
        prefix = ""
        token = MODEL_GETATTR_BEHAVIOR.set("coro")
        try:
            new_result: Any = result
            for part in self_queryset.embed_parent[0].split("__"):
                prefix = f"{prefix}__{part}" if prefix else part
                new_result = getattr(new_result, part)
                if isawaitable(new_result):
                    new_result = await new_result
                if (
                    tables_and_models is not None
                    and mapping is not None
                    and prefix not in seen_prefixes
                    and prefetches_dict
                    and (prefetches_list := prefetches_dict.get(prefix))
                ):
                    await self._apply_prefetches_list(
                        instance=new_result,
                        prefix=prefix,
                        mapping=mapping,
                        tables_and_models=tables_and_models,
                        prefetches=prefetches_list,
                    )
                seen_prefixes.add(prefix)
        finally:
            MODEL_GETATTR_BEHAVIOR.reset(token)
        if mapping is not None and prefetches_dict:
            await self._apply_prefetches_self_and_select_related(
                instance=new_result,
                prefetches_dict=prefetches_dict,
                mapping=mapping,
                tables_and_models=tables_and_models,
                seen=seen_prefixes,
            )
        if self_queryset.embed_parent[1]:
            setattr(new_result, self_queryset.embed_parent[1], result)
        return result, new_result

    def _prepare_prefetches_for_rows(
        self,
        rows: Sequence[sqlalchemy.Row],
    ) -> dict[str, list[Prefetch]]:
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
        self_queryset = cast("QuerySet[EdgyModel, EdgyEmbedTarget]", self)
        prepared_prefetches: dict[str, list[Prefetch]] = {}
        seen_prefetches: set[tuple[None | int, str, str, str]] = set()

        for prefetch in self_queryset._prefetch_related:
            compare_tuple = (
                id(prefetch.queryset) if prefetch.queryset is not None else None,
                prefetch.related_name,
                prefetch.anchor_path,
                prefetch.to_attr,
            )
            if compare_tuple in seen_prefetches:
                continue
            else:
                seen_prefetches.add(compare_tuple)
            target_crawl_result = crawl_relationship(
                self_queryset.model_class, prefetch.to_attr, allow_crossing_db=True
            )
            anchor_crawl_result = crawl_relationship(
                self_queryset.model_class,
                prefetch.anchor_path,
                allow_crossing_db=True,
                traverse_last=True,
            )

            prefetch_crawl_result = crawl_relationship(
                anchor_crawl_result.model_class, prefetch.related_name, traverse_last=True
            )
            if prefetch_crawl_result.cross_db_remainder:
                raise NotImplementedError(
                    "Cannot prefetch from other db yet. Maybe in future this feature will be added."
                )
            if prefetch_crawl_result.reverse_path is False:
                raise QuerySetError(
                    detail=("Creating a reverse path is not possible, unidirectional fields used.")
                )

            prefetch.check_for_collision(anchor_crawl_result.model_class)
            new_prefetch = Prefetch(
                related_name=prefetch.related_name,
                to_attr=prefetch.to_attr,
                anchor_path=prefetch.anchor_path,
            )

            prefetch_queryset: QuerySet | None = prefetch.queryset

            clauses = [
                {
                    f"{prefetch_crawl_result.reverse_path}__{pkcol}": row._mapping[pkcol]
                    for pkcol in anchor_crawl_result.model_class.pkcolumns
                }
                for row in rows
            ]
            if prefetch_queryset is None:
                prefetch_queryset = prefetch_crawl_result.model_class.query.local_or(*clauses)
            else:
                prefetch_queryset = prefetch_queryset.local_or(*clauses)

            prefetch_queryset = prefetch_queryset.select_related(
                prefetch_crawl_result.reverse_path
            )
            # the assigned queryset has an empty cache
            new_prefetch.queryset = prefetch_queryset
            new_prefetch._reverse_path_to_anchor = prefetch_crawl_result.reverse_path
            if new_prefetch.anchor_path:
                new_prefetch._forward_path = (
                    f"{new_prefetch.anchor_path}__{target_crawl_result.forward_path}"
                )
            else:
                new_prefetch._forward_path = target_crawl_result.forward_path
            new_prefetch._baking_finished = asyncio.Event()
            new_prefetch._target_model = cast("type[Model]", target_crawl_result.model_class)
            new_prefetch._baked_results = {}
            prepared_prefetches.setdefault(new_prefetch._forward_path, []).append(new_prefetch)
        return prepared_prefetches

    def prefetch_related(self, *prefetch: Prefetch) -> QuerySet[EdgyModel, EdgyEmbedTarget]:
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
        self_queryset = cast("QuerySet[EdgyModel, EdgyEmbedTarget]", self)
        queryset: QuerySet = self_queryset._clone()

        # Validate that all provided arguments are instances of Prefetch.
        if any(not isinstance(value, Prefetch) for value in prefetch):
            raise QuerySetError("The prefetch_related must have Prefetch type objects only.")

        # Append the new prefetch objects to the queryset's internal list.
        queryset._prefetch_related = [*self_queryset._prefetch_related, *prefetch]
        return queryset
