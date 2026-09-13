from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Mapping, Sequence
from inspect import isawaitable
from typing import TYPE_CHECKING, Any, Generic, cast, overload

import sqlalchemy

from edgy.core.db.context_vars import MODEL_GETATTR_BEHAVIOR
from edgy.core.db.querysets.prefetch import Prefetch
from edgy.core.db.querysets.types import EdgyEmbedTarget, EdgyModel, tables_and_models_type
from edgy.core.utils.concurrency import run_concurrently
from edgy.core.utils.db import get_table_key_or_name
from edgy.exceptions import QuerySetError

from ..clauses import clean_path_to_crawl_result

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

    def _apply_prefetches_list(
        self,
        *,
        instance: BaseModelType,
        prefetches: Sequence[Prefetch],
        mapping: Mapping,
        prefix: str = "",
        # if not provided we use row_prefix = "", required for embedding
        tables_and_models: tables_and_models_type | None = None,
    ) -> None:
        """Apply prefetches to a specific model instance."""
        for related in prefetches:
            # Check for conflicting names early to prevent unexpected overwrites.
            related.check_for_collision(model=instance)
            reduced_prefix = prefix.removesuffix(related._forward_path_to_anchor).removesuffix(
                "__"
            )
            # tables can be alias
            row_prefix = (
                f"{get_table_key_or_name(tables_and_models[reduced_prefix][0])}_"
                if reduced_prefix and tables_and_models
                else ""
            )
            model_key = related._target_model.create_model_key_from_raw_mapping(
                mapping=mapping, prefix=row_prefix
            )
            # Ensure it is in the baked results.
            related._baked_results.setdefault(model_key, [])
            new_attr_name = related.to_attr.rsplit("__", 1)[-1]
            object.__setattr__(instance, new_attr_name, list(related._baked_results[model_key]))

    async def _apply_prefetches_self_and_select_related(
        self,
        *,
        instance: EdgyModel,
        prefetches_dict: dict[str, list[Prefetch]],
        mapping: Mapping,
        tables_and_models: tables_and_models_type | None,
        seen: set[str],
    ) -> None:
        """Apply prefetches on select related branches.

        This method applies prefetching logic to the current queryset by considering
        select related relationships and embedding targets. It handles fetching related
        data concurrently and embedding parents in the result set.

        Args:
            instance: The current EdgyModel instance.
            prefetches_dict: A dictionary mapping relationship or embedding paths to lists of Prefetch objects.
            mapping: The mapping object used for database operations.
            tables_and_models: Optional tables and models information.
            seen: A set tracking already processed prefixes to prevent redundant fetches.

        Returns:
            None
        """
        self_queryset = cast("QuerySet[EdgyModel, EdgyEmbedTarget]", self)
        token = MODEL_GETATTR_BEHAVIOR.set("passdown")
        try:
            if "" not in seen and (prefetches_list := prefetches_dict.get("")):
                seen.add("")
                await run_concurrently(
                    [prefetch._init_bake() for prefetch in prefetches_list],
                    limit=1 if getattr(self_queryset.database, "force_rollback", False) else None,
                )
                self._apply_prefetches_list(
                    instance=instance,
                    mapping=mapping,
                    tables_and_models=tables_and_models,
                    prefetches=prefetches_list,
                )
            # we need only to check the automatically generated embedding.
            for path in sorted(
                self_queryset._select_related_embedding, key=lambda x: x.count("__"), reverse=True
            ):
                prefix = ""
                current_instance: BaseModelType | None = instance
                for part in path.split("__"):
                    prefix = f"{prefix}__{part}" if prefix else part
                    if prefix in seen:
                        continue
                    current_instance = cast(
                        "BaseModelType | None", getattr(current_instance, part, None)
                    )
                    seen.add(prefix)
                    if current_instance is None:
                        break
                    if prefetches_list := prefetches_dict.get(prefix):
                        await run_concurrently(
                            [prefetch._init_bake() for prefetch in prefetches_list],
                            limit=1
                            if getattr(self_queryset.database, "force_rollback", False)
                            else None,
                        )
                        self._apply_prefetches_list(
                            instance=current_instance,
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
        This is a result transformation and apply prefetches.
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
                # if (
                #     tables_and_models is not None
                #     and mapping is not None
                #     and prefix not in seen_prefixes
                #     and prefetches_dict
                #     and (prefetches_list := prefetches_dict.get(prefix))
                # ):
                #     await self._apply_prefetches_list(
                #         instance=new_result,
                #         mapping=mapping,
                #         prefetches=prefetches_list,
                #         # not in select related, don't provide prefix
                #     )
                # seen_prefixes.add(prefix)
        finally:
            MODEL_GETATTR_BEHAVIOR.reset(token)
        if self_queryset.embed_parent[1]:
            setattr(new_result, self_queryset.embed_parent[1], result)
        return result, new_result

    def _prepare_prefetches_for_rows(
        self, rows: Sequence[sqlalchemy.Row], tables_and_models: tables_and_models_type
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
                prefetch.from_anchor,
                prefetch.to_attr,
            )
            if compare_tuple in seen_prefetches:
                continue
            else:
                seen_prefetches.add(compare_tuple)
            target_crawl_result = clean_path_to_crawl_result(
                self_queryset.model_class,
                prefetch.to_attr,
                embed_parent=self.embed_parent_filters,
                # allow_crossing_db=True,
                # no_operator=True,
            )
            anchor_crawl_result = clean_path_to_crawl_result(
                self_queryset.model_class,
                prefetch.from_anchor,
                embed_parent=self.embed_parent_filters,
                model_database=self.database,
                path_to_field=False,
                # allow_crossing_db=True,
                # traverse_last=True,
                # no_operator=True,
            )
            if anchor_crawl_result.cross_db_remainder:
                raise NotImplementedError(
                    "Cannot prefetch from other db yet. Maybe in future this feature will be added."
                )

            prefetch_crawl_result = clean_path_to_crawl_result(
                anchor_crawl_result.model_class,
                prefetch.related_name,
                path_to_field=False,
                embed_parent=self.embed_parent_filters,
                # traverse_last=True,
                # no_operator=True,
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
                from_anchor=prefetch.from_anchor,
            )

            prefetch_queryset: QuerySet | None = prefetch.queryset
            row_prefix = (
                f"{tables_and_models[anchor_crawl_result.forward_path][0].name}_"
                if anchor_crawl_result.forward_path
                else ""
            )
            clauses = [
                {
                    f"{prefetch_crawl_result.reverse_path}__{pkcol}": row._mapping[
                        f"{row_prefix}{pkcol}"
                    ]
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
            new_prefetch.forward_path = prefetch.forward_path
            new_prefetch._forward_path_to_anchor = prefetch_crawl_result.forward_path
            new_prefetch._reverse_path_to_anchor = prefetch_crawl_result.reverse_path
            new_prefetch._baking_finished = asyncio.Event()
            new_prefetch._target_model = cast("type[Model]", target_crawl_result.model_class)
            new_prefetch._baked_results = {}
            prepared_prefetches.setdefault(new_prefetch.forward_path, []).append(new_prefetch)
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
        select_pathes: set[str] = set()
        # this one extra doesn't matter much from performance perspective, is maybe even cheaper
        if queryset.embed_parent and queryset.embed_parent[0]:
            # parsed later
            select_pathes.add(queryset.embed_parent[0])
        # now add the forward pathes
        select_pathes.update(
            prefetch.forward_path
            for prefetch in queryset._prefetch_related
            if prefetch.forward_path
        )
        # they are sanitized and analyzed later in _update_select_related_weak
        queryset._update_select_related_weak(
            select_pathes, cache_name="_select_related_embedding", clear=True
        )
        return queryset

    @overload
    def update_embed_parent(self, embed_parent: None) -> QuerySet[EdgyModel, EdgyModel]: ...
    @overload
    def update_embed_parent(
        self, embed_parent: tuple[str, str]
    ) -> QuerySet[EdgyModel, EdgyEmbedTarget]: ...
    def update_embed_parent(
        self, embed_parent: tuple[str, str] | None
    ) -> QuerySet[EdgyModel, EdgyEmbedTarget] | QuerySet[EdgyModel, EdgyModel]:
        """
        Update or remove (provide None) embed_parent applied on instances.
        Note: this doesn't affect embed_parent for filters.

        Args:
            embed_parent: define the new embed_parent.
        Returns:
            QuerySetType: A new QuerySet instance with the new embedding.
        """
        self_queryset = cast("QuerySet[EdgyModel, EdgyEmbedTarget]", self)
        queryset = self_queryset._clone()
        queryset.embed_parent = embed_parent
        select_pathes: set[str] = set()
        if queryset.embed_parent and queryset.embed_parent[0]:
            # just add them, they are parsed later
            select_pathes.add(queryset.embed_parent[0])

        if (
            queryset._update_select_related_weak(
                select_pathes,
                cache_name="_select_related_embedding",
                clear=True,
            )
            and queryset._prefetch_related
        ):
            # regenerate prefetch pathes

            queryset._update_select_related_weak(
                (
                    prefetch.forward_path
                    for prefetch in queryset._prefetch_related
                    if prefetch.forward_path
                ),
                cache_name="_select_related_embedding",
                clear=False,
            )
        return queryset
