from __future__ import annotations

import warnings
from collections.abc import (
    AsyncIterator,
    Awaitable,
    Callable,
    Iterable,
    Sequence,
)
from functools import cached_property
from inspect import isawaitable
from itertools import chain
from typing import (
    TYPE_CHECKING,
    Any,
    Literal,
    cast,
)

import orjson
import sqlalchemy

from edgy.core.db.context_vars import MODEL_GETATTR_BEHAVIOR, get_schema
from edgy.core.db.datastructures import QueryModelResultCache
from edgy.core.db.fields.base import BaseForeignKey
from edgy.core.db.models.types import BaseModelType
from edgy.core.db.relationships.utils import crawl_relationship
from edgy.exceptions import QuerySetError
from edgy.types import Undefined

from . import clauses as clauses_mod
from .compiler import QueryCompiler
from .executor import QueryExecutor, get_current_row
from .mixins import QuerySetPropsMixin, TenancyMixin
from .parser import ResultParser
from .prefetch import Prefetch, PrefetchMixin
from .types import (
    EdgyModel,
    QuerySetType,
    reference_select_type,
    tables_and_models_type,
)

if TYPE_CHECKING:  # pragma: no cover
    from edgy.core.connection import Database
    from edgy.core.db.fields.types import BaseFieldType
    from edgy.core.db.querysets.queryset import QuerySet

_empty_set = cast(Sequence[Any], frozenset())


def _extract_unique_lookup_key(obj: Any, unique_fields: Sequence[str]) -> tuple | None:
    """
    Extracts a unique lookup key from an object or dictionary.
    (Helper function, stays in base)
    """
    lookup_key = []
    if isinstance(obj, dict):
        for field in unique_fields:
            if field not in obj:
                return None
            value = obj[field]
            lookup_key.append(
                orjson.dumps(value, option=orjson.OPT_SORT_KEYS)
                if isinstance(value, dict | list)
                else value
            )
    else:
        for field in unique_fields:
            if not hasattr(obj, field):
                return None
            value = getattr(obj, field)
            lookup_key.append(
                orjson.dumps(value, option=orjson.OPT_SORT_KEYS)
                if isinstance(value, dict | list)
                else value
            )
    return tuple(lookup_key)


class BaseQuerySet(
    TenancyMixin,
    QuerySetPropsMixin,
    PrefetchMixin,
    QuerySetType,
):
    """
    Internal definitions for queryset.
    This is now a "Facade" that holds state and delegates work.
    """

    def __init__(
        self,
        model_class: type[BaseModelType] | None = None,
        *,
        database: Database | None = None,
        filter_clauses: Iterable[Any] = _empty_set,
        select_related: Iterable[str] = _empty_set,
        prefetch_related: Iterable[Prefetch] = _empty_set,
        limit_count: int | None = None,
        limit: int | None = None,
        limit_offset: int | None = None,
        offset: int | None = None,
        batch_size: int | None = None,
        order_by: Iterable[str] = _empty_set,
        group_by: Iterable[str] = _empty_set,
        distinct_on: None | Literal[True] | Iterable[str] = None,
        distinct: None | Literal[True] | Iterable[str] = None,
        only_fields: Iterable[str] | None = None,
        only: Iterable[str] = _empty_set,
        defer_fields: Sequence[str] | None = None,
        defer: Iterable[str] = _empty_set,
        embed_parent: tuple[str, str | str] | None = None,
        using_schema: str | None | Any = Undefined,
        table: sqlalchemy.Table | None = None,
        exclude_secrets: bool = False,
        extra_select: Iterable[sqlalchemy.ClauseElement] | None = None,
        reference_select: reference_select_type | None = None,
    ) -> None:
        if model_class.__is_proxy_model__:
            model_class = model_class.__parent__

        super().__init__(model_class=model_class)
        self.filter_clauses: list[Any] = list(filter_clauses)
        self.or_clauses: list[Any] = []
        self._aliases: dict[str, sqlalchemy.Alias] = {}
        if limit_count is not None:
            warnings.warn(
                "`limit_count` is deprecated use `limit`", DeprecationWarning, stacklevel=2
            )
            limit = limit_count
        self.limit_count = limit
        if limit_offset is not None:
            warnings.warn(
                "`limit_offset` is deprecated use `limit`", DeprecationWarning, stacklevel=2
            )
            offset = limit_offset
        self._offset = offset
        select_related = set(select_related)
        self._select_related: set[str] = set()
        self._select_related_weak: set[str] = set()
        if select_related:
            self._update_select_related(select_related)
        self._prefetch_related = list(prefetch_related)
        self._batch_size = batch_size
        self._order_by: tuple[str, ...] = tuple(order_by)
        self._group_by: tuple[str, ...] = tuple(group_by)
        if distinct_on is not None:
            warnings.warn(
                "`distinct_on` is deprecated use `distinct`", DeprecationWarning, stacklevel=2
            )
            distinct = distinct_on

        if distinct is True:
            distinct = _empty_set
        self.distinct_on = list(distinct) if distinct is not None else None
        if only_fields is not None:
            warnings.warn(
                "`only_fields` is deprecated use `only`", DeprecationWarning, stacklevel=2
            )
            only = only_fields
        self._only = set(only)
        if defer_fields is not None:
            warnings.warn(
                "`defer_fields` is deprecated use `defer`", DeprecationWarning, stacklevel=2
            )
            defer = defer_fields
        self._defer = set(defer)
        self.embed_parent = embed_parent
        self.embed_parent_filters: tuple[str, str | str] | None = None
        self.using_schema = using_schema
        self._extra_select = list(extra_select) if extra_select is not None else []
        self._reference_select = (
            reference_select.copy() if isinstance(reference_select, dict) else {}
        )
        self._exclude_secrets = exclude_secrets
        self._cache = QueryModelResultCache(attrs=self.model_class.pkcolumns)
        self._clear_cache(keep_result_cache=False)
        self._cached_select_related_expression: (
            tuple[Any, dict[str, tuple[sqlalchemy.Table, type[BaseModelType]]]] | None
        ) = None
        self.active_schema = self.get_schema()
        self._for_update: dict[str, Any] | None = None

        if table is not None:
            self.table = table
        if database is not None:
            self.database = database

    def _clone(self) -> QuerySet:
        """
        This is core to the builder pattern
        """
        queryset = self.__class__(
            self.model_class,
            database=getattr(self, "_database", None),
            filter_clauses=self.filter_clauses,
            prefetch_related=self._prefetch_related,
            limit=self.limit_count,
            offset=self._offset,
            batch_size=self._batch_size,
            order_by=self._order_by,
            group_by=self._group_by,
            distinct=self.distinct_on,
            only=self._only,
            defer=self._defer,
            embed_parent=self.embed_parent,
            using_schema=self.using_schema,
            table=getattr(self, "_table", None),
            exclude_secrets=self._exclude_secrets,
            reference_select=self._reference_select,
            extra_select=self._extra_select,
        )
        queryset.or_clauses.extend(self.or_clauses)
        queryset.embed_parent_filters = self.embed_parent_filters
        queryset._select_related.update(self._select_related)
        queryset._select_related_weak.update(self._select_related_weak)
        queryset._cached_select_related_expression = self._cached_select_related_expression
        queryset._for_update = self._for_update.copy() if self._for_update is not None else None
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
        self._cache_first: tuple[BaseModelType, Any] | None = None
        self._cache_last: tuple[BaseModelType, Any] | None = None
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
            self.model_class, kwargs, self.embed_parent_filters, model_database=self.database
        )

        for key, value in cleaned_kwargs.items():
            model_class, field_name, op, related_str, _, cross_db_remainder = crawl_relationship(
                self.model_class, key
            )
            if related_str:
                select_related.add(related_str)
            field = model_class.meta.fields.get(field_name, clauses_mod.generic_field)
            if cross_db_remainder:
                assert field is not clauses_mod.generic_field
                fk_field = cast(BaseForeignKey, field)
                sub_query = (
                    fk_field.target.query.filter(**{cross_db_remainder: value})
                    .only(*fk_field.related_columns.keys())
                    .values_list(fields=fk_field.related_columns.keys())
                )

                async def wrapper(
                    queryset: QuerySet,
                    tables_and_models: tables_and_models_type,
                    *,
                    _field: BaseFieldType = field,
                    _sub_query: QuerySet = sub_query,
                    _prefix: str = related_str,
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
                    _op: str | None = op,
                    _prefix: str = related_str,
                    _field_name: str = field_name,
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
            embed_parent=self.embed_parent_filters,
            model_database=self.database,
        )
        order_col = tables_and_models[crawl_result.forward_path][0].columns[
            crawl_result.field_name
        ]
        return order_col.desc() if reverse else order_col

    def _update_select_related_weak(self, fields: Iterable[str], *, clear: bool) -> bool:
        related: set[str] = set()
        for field_name in fields:
            field_name = field_name.lstrip("-")
            related_element = clauses_mod.clean_path_to_crawl_result(
                self.model_class,
                path=field_name,
                embed_parent=self.embed_parent_filters,
                model_database=self.database,
            ).forward_path
            if related_element:
                related.add(related_element)
        if related and not self._select_related.union(self._select_related_weak).issuperset(
            related
        ):
            self._cached_select_related_expression = None
            if clear:
                self._select_related_weak.clear()
            self._select_related_weak.update(related)
            return True
        return False

    def _update_select_related(self, pathes: Iterable[str]) -> None:
        related: set[str] = set()
        for path in pathes:
            path = path.lstrip("-")
            crawl_result = clauses_mod.clean_path_to_crawl_result(
                self.model_class,
                path=path,
                embed_parent=self.embed_parent_filters,
                model_database=self.database,
            )
            related_element = (
                crawl_result.field_name
                if not crawl_result.forward_path
                else f"{crawl_result.forward_path}__{crawl_result.field_name}"
            )
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
            embed_parent=self.embed_parent_filters,
            model_database=self.database,
        )
        return tables_and_models[crawl_result.forward_path][0].columns[crawl_result.field_name]

    async def _embed_parent_in_result(
        self, result: EdgyModel | Awaitable[EdgyModel]
    ) -> tuple[EdgyModel, Any]:
        """
        This is a result transformation, called by the Parser.
        """
        if isawaitable(result):
            result = await result
        if not self.embed_parent:
            return result, result
        token = MODEL_GETATTR_BEHAVIOR.set("coro")
        try:
            new_result: Any = result
            for part in self.embed_parent[0].split("__"):
                new_result = getattr(new_result, part)
                if isawaitable(new_result):
                    new_result = await new_result
        finally:
            MODEL_GETATTR_BEHAVIOR.reset(token)
        if self.embed_parent[1]:
            setattr(new_result, self.embed_parent[1], result)
        return result, new_result

    def get_schema(self) -> str | None:
        schema = self.using_schema
        if schema is Undefined:
            schema = get_schema()
        if schema is None:
            schema = self.model_class.get_db_schema()
        return schema

    @property
    def _current_row(self) -> sqlalchemy.Row | None:
        """(Refactored: Delegates to the helper in executor.py)"""
        return get_current_row()

    async def _execute_iterate(
        self, fetch_all_at_once: bool = False
    ) -> AsyncIterator[BaseModelType]:
        """
        (Refactored: Now delegates to the Executor)
        """
        # Create the specialists
        compiler = QueryCompiler(self)
        parser = ResultParser(self)
        executor = QueryExecutor(self, compiler, parser)

        # Delegate the work
        async for model in executor.iterate(fetch_all_at_once=fetch_all_at_once):  # type: ignore
            yield model

    async def _execute_all(self) -> list[EdgyModel]:
        """
        Still relies on _execute_iterate.
        """
        return [result async for result in self._execute_iterate(fetch_all_at_once=True)]

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
            | QuerySet
        ],
        exclude: bool = False,
        or_: bool = False,
        allow_global_or: bool = True,
    ) -> QuerySet:
        """
        This is the core 'filter' builder logic.
        """
        from edgy.core.db.querysets.queryset import QuerySet

        queryset: QuerySet = self._clone()
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
        self, use_models: bool = False, remove_referenced_call: str | bool = False
    ) -> int:
        """
        (Refactored: Now delegates to the Executor)
        """
        # We must create new specialists *every time* because the queryset
        # state might have changed (e.g., in _model_based_delete)
        compiler = QueryCompiler(self)
        parser = ResultParser(self)  # Delete doesn't use parser, but good practice
        executor = QueryExecutor(self, compiler, parser)

        return await executor.delete(
            use_models=use_models, remove_referenced_call=remove_referenced_call
        )

    async def _get_raw(self, **kwargs: Any) -> tuple[BaseModelType, Any]:
        """
        (Refactored: Builder logic stays, execution logic delegates)
        """
        if kwargs:
            cached = cast(
                tuple[BaseModelType, Any] | None, self._cache.get(self.model_class, kwargs)
            )
            if cached is not None:
                return cached
            filter_query = cast("BaseQuerySet", self.filter(**kwargs))
            filter_query._cache = self._cache
            return await filter_query._get_raw()
        elif self._cache_count == 1:
            if self._cache_first is not None:
                return self._cache_first
            elif self._cache_last is not None:
                return self._cache_last

        compiler = QueryCompiler(self)
        parser = ResultParser(self)
        executor = QueryExecutor(self, compiler, parser)
        return await executor.get_one()
