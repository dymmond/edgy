from __future__ import annotations

import functools
import warnings
from collections.abc import (
    AsyncIterator,
    Awaitable,
    Callable,
    Iterable,
    Sequence,
)
from contextvars import ContextVar
from functools import cached_property
from itertools import chain
from typing import (
    TYPE_CHECKING,
    Any,
    Generic,
    cast,
)

import sqlalchemy

from edgy.core.db.context_vars import get_schema
from edgy.core.db.datastructures import QueryModelResultCache
from edgy.core.db.fields.base import BaseForeignKey
from edgy.core.db.models.types import BaseModelType
from edgy.core.db.relationships.utils import crawl_relationship
from edgy.exceptions import QuerySetError
from edgy.types import Undefined

from . import clauses as clauses_mod
from .compiler import QueryCompiler
from .executor import QueryExecutor
from .mixins import EmbeddingMixin, QuerySetPropsMixin, TenancyMixin
from .types import (
    EdgyEmbedTarget,
    EdgyModel,
    QuerySetType,
    reference_select_type,
    tables_and_models_type,
)

if TYPE_CHECKING:  # pragma: no cover
    from edgy.core.connection import Database
    from edgy.core.db.fields.types import BaseFieldType

    from .prefetch import Prefetch
    from .queryset import QuerySet

_empty_set = cast(set[Any], frozenset())
_injected_filters_deletion: ContextVar[Iterable] = ContextVar(
    "_injected_filters_deletion", default=()
)


def _deprecated_init_fixup(fn: Any) -> Callable:
    @functools.wraps(fn)
    def _(self: Any, *args: Any, **kwargs: Any) -> None:
        if args:
            warnings.warn(
                "`model_class` is now keyword-only.",
                DeprecationWarning,
                stacklevel=2,
            )
            kwargs["model_class"] = args[0]
            fn(self, *args[1:], **kwargs)
        else:
            fn(self, *args, **kwargs)

    return _


class BaseQuerySet(
    TenancyMixin[EdgyModel, EdgyEmbedTarget],
    EmbeddingMixin[EdgyModel, EdgyEmbedTarget],
    QuerySetPropsMixin,
    QuerySetType[EdgyModel, EdgyEmbedTarget],
    Generic[EdgyModel, EdgyEmbedTarget],
):
    """
    Internal definitions for queryset.
    This is now a "Facade" that holds state and delegates work.
    """

    @_deprecated_init_fixup
    def __init__(
        self, *, model_class: type[EdgyModel], using_schema: None | str, **kwargs: Any
    ) -> None:
        # ensure only the real model_class is used here not a proxy
        if model_class.__is_proxy_model__:
            model_class = cast(type[EdgyModel], model_class.__parent__)

        super().__init__(model_class=model_class)
        if kwargs:
            warnings.warn(
                "Assigning attributes to QuerySet via `__init__` is deprecated and partially broken. "
                "Use methods and when possible attributes on the instance instead. "
                "The only valid keyword only arguments are `model_class` and `using_schema`.",
                DeprecationWarning,
                stacklevel=2,
            )

        self.filter_clauses: list[Any] = (
            list(kwargs["filter_clauses"]) if "filter_clauses" in kwargs else []
        )
        self.or_clauses: list[Any] = []
        self.limit_count: int | None = kwargs.get("limit")
        self._offset: int = kwargs.get("offset", 0)
        self._select_related: set[str] = set()
        # groups and order by
        self._select_related_g_and_o: set[str] = set()
        # embedded, like embed_parent or prefetches
        self._select_related_embedding: set[str] = set()
        self._prefetch_related: tuple[Prefetch, ...] = tuple(
            kwargs.get("prefetch_related", _empty_set)
        )
        self._batch_size: int | None = kwargs.get("batch_size")
        self._order_by: tuple[str, ...] = tuple(kwargs.get("order_by", _empty_set))
        self._group_by: tuple[str, ...] = tuple(kwargs.get("group_by", _empty_set))

        distinct = kwargs.get("distinct")
        if distinct is True:
            distinct = _empty_set
        self.distinct_on: tuple[str, ...] | None = (
            tuple(distinct) if distinct is not None else None
        )
        self._injected_create_handler: (
            Callable[[dict[str, Any] | BaseModelType, Iterable], BaseModelType] | None
        ) = None
        self._only: set[str] = set()
        self._defer: set[str] = set()
        self._embed_parent: tuple[str, str | str] | None = None
        self._embed_parent_filters: tuple[str, str | str] | None = None
        self.using_schema: str | None | Any = using_schema
        self._extra_select: tuple[sqlalchemy.ClauseElement, ...] = tuple(
            kwargs.get("extra_select", _empty_set)
        )
        self._reference_select: reference_select_type = {}
        self._exclude_secrets: bool = kwargs.get("exclude_secrets", False)
        self._cache = QueryModelResultCache(attrs=self.pkcolumns)
        self._clear_cache(keep_result_cache=False)
        self._cached_select_related_expression: (
            tuple[Any, dict[str, tuple[sqlalchemy.Table, type[BaseModelType]]]] | None
        ) = None
        self.active_schema = self.get_schema()
        self._for_update: dict[str, Any] | None = None

        table: sqlalchemy.Table | None = kwargs.get("table")
        if table is not None:
            self.table = table
        database: Database | None = kwargs.get("database")
        if database is not None:
            self.database = database

        self._suppress_pk_deduplication: bool = False

    def _create_clone_instance(self) -> QuerySet[EdgyModel, EdgyEmbedTarget]:
        """Base instance which is decorated later in clone."""
        return cast("type[QuerySet]", type(self))(
            model_class=self.model_class, using_schema=self.using_schema
        )

    def _clone(self) -> QuerySet[EdgyModel, EdgyEmbedTarget]:
        """
        This is core to the builder pattern. Most cache is refreshed

        Note: the _cached_select_related_expression is transferred.
        """
        queryset = self._create_clone_instance()
        queryset._database = getattr(self, "_database", None)
        queryset._table = getattr(self, "_table", None)
        queryset._prefetch_related = self._prefetch_related
        queryset._exclude_secrets = self._exclude_secrets
        # copying won't work, we would need a deep copy but not necessary anyway
        queryset._reference_select = self._reference_select
        queryset._offset = self._offset
        # tuple, so we can just move it
        queryset._order_by = self._order_by
        # tuple, so we can just move it
        queryset._group_by = self._group_by
        # tuple, so we can just move it
        queryset.distinct_on = self.distinct_on
        # tuple, so we can just move it
        queryset._extra_select = self._extra_select
        queryset.limit_count = self.limit_count
        queryset._batch_size = self._batch_size
        queryset.filter_clauses.extend(self.filter_clauses)
        queryset.or_clauses.extend(self.or_clauses)
        # this handles the create arguments
        queryset._injected_create_handler = self._injected_create_handler
        queryset._embed_parent = self._embed_parent
        queryset._embed_parent_filters = self._embed_parent_filters
        queryset._only.update(self._only)
        queryset._defer.update(self._defer)
        queryset._select_related.update(self._select_related)
        queryset._select_related_g_and_o.update(self._select_related_g_and_o)
        queryset._select_related_embedding.update(self._select_related_embedding)
        # by default this is copied, we need to clear it when select_related caches are changing
        queryset._cached_select_related_expression = self._cached_select_related_expression
        queryset._for_update = self._for_update
        return cast("QuerySet", queryset)

    async def _as_select_with_tables(
        self,
    ) -> tuple[Any, tables_and_models_type]:
        """
        (This is the new internal method for the base class)
        Builds the query select by delegating to the QueryCompiler.
        """
        compiler = QueryCompiler(self)
        self._get_join_graph_data()
        expression, tables_and_models = await compiler.build_select()
        return expression, tables_and_models

    @cached_property
    def _has_dynamic_clauses(self) -> bool:
        return any(callable(clause) for clause in chain(self.filter_clauses, self.or_clauses))

    def _clear_cache(
        self, *, keep_result_cache: bool = False, keep_cached_selected: bool = False
    ) -> None:
        if not keep_result_cache:
            self._cache.clear()
        if not keep_cached_selected:
            self._cached_select_with_tables: (
                tuple[Any, dict[str, tuple[sqlalchemy.Table, type[BaseModelType]]]] | None
            ) = None
        self._cache_count: int | None = None
        self._cache_first: tuple[EdgyModel, EdgyEmbedTarget] | None = None
        self._cache_last: tuple[EdgyModel, EdgyEmbedTarget] | None = None
        self._cache_fetch_all: bool = False

    def _build_order_by_iterable(
        self, order_by: Iterable[str], tables_and_models: tables_and_models_type
    ) -> Iterable:
        """
        This is a helper for the *compiler* but is called by it,
         so it's okay for it to live here as it's part of the 'builder' logic.
        """
        return (self._prepare_order_by(entry, tables_and_models) for entry in order_by)

    async def build_where_clause(
        self, _: Any = None, tables_and_models: tables_and_models_type | None = None
    ) -> Any:
        """
        (This method is now a simple forwarder to the Compiler.
         It's kept for API compatibility, e.g. for QuerySet(QuerySet) filters)
        """
        compiler = QueryCompiler(self)
        joins: Any | None = None
        if tables_and_models is None:
            joins, tables_and_models = self._get_join_graph_data()

        return await compiler.build_where_clause(tables_and_models, joins=joins)

    def _validate_only_and_defer(self) -> None:
        if self._only and self._defer:
            raise QuerySetError("You cannot use .only() and .defer() at the same time.")

    def _get_join_graph_data(self) -> tuple[Any, tables_and_models_type]:
        """
        Gets the join graph, building it via the compiler if needed.

        This is the new "bridge" that manages the
        _cached_select_related_expression variable to satisfy brittle tests,
        while keeping the compiler itself stateless.
        """
        if self._cached_select_related_expression is None:
            # Create a compiler just to build the join graph
            compiler = QueryCompiler(self)

            # Call the compiler's build method and cache the result
            self._cached_select_related_expression = compiler.build_join_graph()
        return self._cached_select_related_expression

    async def as_select_with_tables(
        self,
    ) -> tuple[Any, tables_and_models_type]:
        """
        (Refactored: Now delegates to the Compiler)
        """
        if self._cached_select_with_tables is None:
            self._cached_select_with_tables = await self._as_select_with_tables()
        return self._cached_select_with_tables

    async def as_select(
        self,
    ) -> Any:
        return (await self.as_select_with_tables())[0]

    def _kwargs_to_clauses(
        self,
        kwargs: Any,
    ) -> tuple[list[Any], set[str]]:
        """
        This is part of the 'filter' builder logic
        """
        clauses = []
        select_related: set[str] = set()
        cleaned_kwargs = clauses_mod.clean_query_kwargs(
            self.model_class, kwargs, self._embed_parent_filters, model_database=self.database
        )

        for key, value in cleaned_kwargs.items():
            crawl_result = crawl_relationship(self.model_class, key)
            if crawl_result.forward_path:
                select_related.add(crawl_result.forward_path)
            field = crawl_result.model_class.meta.fields.get(
                crawl_result.field_name, clauses_mod.generic_field
            )
            if crawl_result.cross_db_remainder:
                assert field is not clauses_mod.generic_field
                fk_field = cast(BaseForeignKey, field)
                sub_query = (
                    fk_field.target.query.filter(**{crawl_result.cross_db_remainder: value})
                    .only(*fk_field.related_columns.keys())
                    .values_list(fields=fk_field.related_columns.keys())
                )

                async def wrapper(
                    queryset: QuerySet,
                    tables_and_models: tables_and_models_type,
                    *,
                    _field: BaseFieldType = field,
                    _sub_query: QuerySet = sub_query,
                    _prefix: str = crawl_result.forward_path,
                ) -> Any:
                    table = tables_and_models[_prefix][0]
                    fk_tuple = sqlalchemy.tuple_(
                        *(getattr(table.columns, colname) for colname in _field.get_column_names())
                    )
                    return fk_tuple.in_(await _sub_query)

                clauses.append(wrapper)
            else:
                assert not isinstance(value, BaseModelType), (
                    f"should be parsed in clean: {key}: {value}"
                )

                async def wrapper(
                    queryset: QuerySet,
                    tables_and_models: tables_and_models_type,
                    *,
                    _field: BaseFieldType = field,
                    _value: Any = value,
                    _op: str = crawl_result.operator or "exact",
                    _prefix: str = crawl_result.forward_path,
                    _field_name: str = crawl_result.field_name,
                ) -> Any:
                    _value = await clauses_mod.parse_clause_arg(
                        _value, queryset, tables_and_models
                    )
                    table = tables_and_models[_prefix][0]
                    return _field.operator_to_clause(_field_name, _op, table, _value)

                wrapper._edgy_force_callable_queryset_filter = True
                clauses.append(wrapper)

        return clauses, select_related

    def _prepare_order_by(self, order_by: str, tables_and_models: tables_and_models_type) -> Any:
        """
        (Helper for 'order_by' builder logic, but called by compiler)
        """
        reverse = order_by.startswith("-")
        order_by = order_by.lstrip("-")
        crawl_result = clauses_mod.clean_path_to_crawl_result(
            self.model_class,
            path=order_by,
            embed_parent=self._embed_parent_filters,
            model_database=self.database,
        )
        order_col = tables_and_models[crawl_result.forward_path][0].columns[
            crawl_result.field_name
        ]
        return order_col.desc() if reverse else order_col

    def _update_related_weak(self, fields: Iterable[str], *, cache_name: str, clear: bool) -> bool:
        """
        Update the select_related cache with cache_name. This is a special cache,
        which is directly used.

        Warning: Depending of the cache_name, a different normalization strategy is used.

        Args:
            fields: list of field pathes.
        Kwargs:
            cache_name: Select the select_related cache. This also affects the normalization strategy.
            clear: Clear the cache.
        """
        # retrieve the cache from queryset, use cache_name to identify
        cache_weak: set[str] = getattr(self, cache_name)
        # use cache_name to load presets, this allows rapid changes in case of different
        # required cache behaviour and validates the cache name
        match cache_name:
            case "_select_related_embedding":
                related_element_fn: Callable[[str], str] = lambda field_name: field_name
            case "_select_related_g_and_o":
                related_element_fn = lambda field_name: (
                    clauses_mod.clean_path_to_crawl_result(
                        self.model_class,
                        path=field_name,
                        embed_parent=self._embed_parent_filters,
                        model_database=self.database,
                    ).forward_path
                )
            case "_only" | "_defer":
                # crossing the db is no problem, it will just may not work.
                # Because traverse_last is False it works. The last part is treated as field no matter
                # if relationField or not
                related_element_fn = lambda field_name: (
                    clauses_mod.clean_path_to_crawl_result(
                        self.model_class,
                        path=field_name,
                        embed_parent=self._embed_parent_filters,
                        model_database=self.database,
                        allow_crossing_db=True,
                    ).forward_path_to_field
                )
            case _:
                raise QuerySetError(f"Invalid cache (`{cache_name}`) used.")
        new_related: set[str] = set()
        for field_name in fields:
            related_element = related_element_fn(field_name)
            # eliminate empty pathes
            if related_element:
                new_related.add(related_element)
        # check if the caches are the same sets
        if new_related != cache_weak:
            # invalidate _cached_select_related_expression, when not subset
            if not self._select_related.issuperset(new_related):
                self._cached_select_related_expression = None
            # now clear the cache to update, if clear was specified
            if clear:
                cache_weak.clear()
            # and fill it with the new content
            cache_weak.update(new_related)
            # return True if the cache was updated
            return True
        # return False if the cache was not updated
        return False

    def _update_select_related(self, pathes: Iterable[str]) -> None:
        related: set[str] = set()
        for path in pathes:
            crawl_result = clauses_mod.clean_path_to_crawl_result(
                self.model_class,
                path=path,
                embed_parent=self._embed_parent_filters,
                model_database=self.database,
            )
            related_element = crawl_result.forward_path_to_field
            if crawl_result.cross_db_remainder:
                raise QuerySetError(
                    detail=f'Selected path "{related_element}" is on another database.'
                )
            if related_element:
                related.add(related_element)
        if related and not self._select_related.issuperset(related):
            self._cached_select_related_expression = None
            self._select_related.update(related)

    def _prepare_distinct(
        self, distinct_on: str, tables_and_models: tables_and_models_type
    ) -> sqlalchemy.Column:
        """Helper for 'distinct' builder, but called by compiler"""
        crawl_result = clauses_mod.clean_path_to_crawl_result(
            self.model_class,
            path=distinct_on,
            embed_parent=self._embed_parent_filters,
            model_database=self.database,
        )
        return tables_and_models[crawl_result.forward_path][0].columns[crawl_result.field_name]

    def get_schema(self) -> str | None:
        """Retrieve the schema."""
        schema = self.using_schema
        if schema is Undefined:
            schema = get_schema()
        if schema is None:
            schema = self.model_class.get_db_schema()
        return schema

    async def _execute_iterate(
        self, fetch_all_at_once: bool = False
    ) -> AsyncIterator[EdgyEmbedTarget]:
        """
        (Refactored: Now delegates to the Executor)
        """
        # Create the specialists
        executor = QueryExecutor(self)

        # Delegate the work
        async for tup in executor.iterate(fetch_all_at_once=fetch_all_at_once):
            yield tup[1]

    async def _execute_all(self) -> list[EdgyEmbedTarget]:
        """
        Resolves to an array and deduplicate.
        """
        executor = QueryExecutor(self)
        results = [result async for result in executor.iterate(fetch_all_at_once=True)]

        if len(results) > 1 and not getattr(self, "_suppress_pk_deduplication", False):
            seen: set[tuple] = set()
            unique = []

            for tup in results:
                try:
                    key = tup[0].create_model_key()
                except AttributeError:
                    # The returned object does not expose the model_class PK attrs;
                    # this can happen in advanced/embedded scenarios. In that case
                    # we bail out and keep the original list to avoid breaking
                    # existing behaviour.
                    return [tup[1] for tup in results]

                if key not in seen:
                    seen.add(key)
                    unique.append(tup[1])

            return unique

        return [tup[1] for tup in results]

    def _filter_or_exclude(
        self,
        kwargs: Any,
        clauses: Sequence[
            sqlalchemy.sql.expression.BinaryExpression
            | Callable[
                [QuerySetType],
                sqlalchemy.sql.expression.BinaryExpression
                | Awaitable[sqlalchemy.sql.expression.BinaryExpression],
            ]
            | dict[str, Any]
            | QuerySetType
        ],
        exclude: bool = False,
        or_: bool = False,
        allow_global_or: bool = True,
    ) -> QuerySet[EdgyModel, EdgyEmbedTarget]:
        """
        This is the core 'filter' builder logic.
        """
        from edgy.core.db.querysets.queryset import QuerySet

        queryset = self._clone()
        if kwargs:
            clauses = [*clauses, kwargs]
        converted_clauses: Sequence[
            sqlalchemy.sql.expression.BinaryExpression
            | Callable[
                [QuerySetType],
                sqlalchemy.sql.expression.BinaryExpression
                | Awaitable[sqlalchemy.sql.expression.BinaryExpression],
            ]
        ] = []
        for raw_clause in clauses:
            if isinstance(raw_clause, dict):
                extracted_clauses, related = queryset._kwargs_to_clauses(kwargs=raw_clause)
                if not queryset._select_related.issuperset(related):
                    queryset._select_related.update(related)
                    queryset._cached_select_related_expression = None
                if or_ and extracted_clauses:
                    wrapper_and = clauses_mod.and_(*extracted_clauses, no_select_related=True)

                    if allow_global_or and len(clauses) == 1:
                        # Global OR mode: promote existing AND filters into the OR group.
                        # This turns:
                        #   qs.filter(A).or_(B)
                        # into:
                        #   OR( AND(A), AND(B) )
                        # instead of: OR(B) AND A.
                        assert not exclude

                        if queryset.filter_clauses:
                            # Wrap existing filters into a single AND group and move them to or_clauses
                            existing_and = clauses_mod.and_(
                                *queryset.filter_clauses, no_select_related=True
                            )
                            queryset.or_clauses.append(existing_and)
                            # Clear filter_clauses so they are not ANDed again later
                            queryset.filter_clauses = []

                        # Add the new OR operand
                        queryset.or_clauses.append(wrapper_and)
                        return queryset

                    # Non-global OR (e.g. local_or) or multiple clauses:
                    # just collect and handle them at the end as a local OR group.
                    converted_clauses.append(wrapper_and)
                else:
                    converted_clauses.extend(extracted_clauses)
            elif isinstance(raw_clause, QuerySet):
                assert raw_clause.model_class is queryset.model_class, (
                    f"QuerySet arg has wrong model_class {raw_clause.model_class}"
                )
                converted_clauses.append(raw_clause.build_where_clause)
                if not queryset._select_related.issuperset(raw_clause._select_related):
                    queryset._select_related.update(raw_clause._select_related)
                    queryset._cached_select_related_expression = None
            else:
                clause = raw_clause

                # Support global OR mode for non-dict clauses (e.g. Q objects, raw callables)
                if or_ and allow_global_or and len(clauses) == 1:
                    # Global OR only makes sense for non-exclude queries
                    assert not exclude

                    # If there are existing AND filters, promote them into the OR group
                    if queryset.filter_clauses:
                        existing_and = clauses_mod.and_(
                            *queryset.filter_clauses,
                            no_select_related=True,
                        )
                        queryset.or_clauses.append(existing_and)
                        queryset.filter_clauses = []

                    # Propagate select_related coming from this clause, if any
                    if hasattr(clause, "_edgy_calculate_select_related"):
                        select_related_calculated = clause._edgy_calculate_select_related(queryset)
                        if not queryset._select_related.issuperset(select_related_calculated):
                            queryset._select_related.update(select_related_calculated)
                            queryset._cached_select_related_expression = None

                    # Add this clause as a new OR branch and return immediately
                    queryset.or_clauses.append(clause)
                    return queryset

                # Normal path (no global OR promotion)
                converted_clauses.append(clause)
                if hasattr(clause, "_edgy_calculate_select_related"):
                    select_related_calculated = clause._edgy_calculate_select_related(queryset)
                    if not queryset._select_related.issuperset(select_related_calculated):
                        queryset._select_related.update(select_related_calculated)
                        queryset._cached_select_related_expression = None
        if not converted_clauses:
            return queryset

        if exclude:
            op = clauses_mod.and_ if not or_ else clauses_mod.or_

            queryset.filter_clauses.append(
                clauses_mod.not_(
                    op(*converted_clauses, no_select_related=True), no_select_related=True
                )
            )
        elif or_:
            queryset.filter_clauses.append(
                clauses_mod.or_(*converted_clauses, no_select_related=True)
            )
        else:
            queryset.filter_clauses.extend(converted_clauses)
        return queryset

    async def raw_delete(
        self, *, use_models: bool = False, remove_referenced_call: str | bool = False
    ) -> int | None:
        """
        Internal delete method.

        Exposes remove_referenced_call and doesn't raise an extra signal.

        Delegates to QueryExecutor.delete.
        """
        # We must create new executors *every time* because the queryset
        # state might have changed (e.g., in _model_based_delete)
        executor = QueryExecutor(self)

        return await executor.delete(
            use_models=use_models,
            remove_referenced_call=remove_referenced_call,
            injected_filters=_injected_filters_deletion.get(),
        )

    async def _get_raw(
        self, kwargs: dict | None = None, no_update_result_cache: bool = False
    ) -> tuple[EdgyModel, EdgyEmbedTarget]:
        """
        Base method used by get like methods.
        """
        if kwargs:
            cached = cast(
                "tuple[EdgyModel, EdgyEmbedTarget] | None",
                self._cache.get(self.model_class, kwargs),
            )
            if cached is not None:
                return cached
            filter_query = cast("BaseQuerySet", self.filter(**kwargs))
            filter_query._cache = self._cache
            return await filter_query._get_raw(no_update_result_cache=no_update_result_cache)
        elif self._cache_count == 1:
            if self._cache_first is not None:
                return self._cache_first
            elif self._cache_last is not None:
                return self._cache_last
        executor = QueryExecutor(self)
        return await executor.get_one(no_update_result_cache=no_update_result_cache)
