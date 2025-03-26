from __future__ import annotations

import warnings
from collections.abc import AsyncGenerator, AsyncIterator, Awaitable, Generator, Iterable, Sequence
from contextvars import ContextVar
from functools import cached_property
from inspect import isawaitable
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Literal,
    Optional,
    Union,
    cast,
)

import orjson
import sqlalchemy

from edgy.core.db.context_vars import CURRENT_INSTANCE, MODEL_GETATTR_BEHAVIOR, get_schema
from edgy.core.db.datastructures import QueryModelResultCache
from edgy.core.db.fields import CharField, TextField
from edgy.core.db.fields.base import BaseForeignKey, RelationshipField
from edgy.core.db.models.model_reference import ModelRef
from edgy.core.db.models.types import BaseModelType
from edgy.core.db.models.utils import apply_instance_extras
from edgy.core.db.relationships.utils import crawl_relationship
from edgy.core.utils.db import CHECK_DB_CONNECTION_SILENCED, check_db_connection, hash_tablekey
from edgy.core.utils.sync import run_sync
from edgy.exceptions import MultipleObjectsReturned, ObjectNotFound, QuerySetError
from edgy.types import Undefined

from . import clauses as clauses_mod
from .mixins import QuerySetPropsMixin, TenancyMixin
from .prefetch import Prefetch, PrefetchMixin, check_prefetch_collision
from .types import (
    EdgyEmbedTarget,
    EdgyModel,
    QuerySetType,
    reference_select_type,
    tables_and_models_type,
)

if TYPE_CHECKING:  # pragma: no cover
    from databasez.core.transaction import Transaction

    from edgy.core.connection import Database
    from edgy.core.db.fields.types import BaseFieldType


_empty_set = cast(Sequence[Any], frozenset())
# get current row during iteration. Used for prefetching.
_current_row_holder: ContextVar[Optional[list[Optional[sqlalchemy.Row]]]] = ContextVar(
    "_current_row_holder", default=None
)


def get_table_key_or_name(table: Union[sqlalchemy.Table, sqlalchemy.Alias]) -> str:
    try:
        return table.key  # type: ignore
    except AttributeError:
        # alias
        return table.name


def _extract_unique_lookup_key(obj: Any, unique_fields: Sequence[str]) -> Union[tuple, None]:
    lookup_key = []
    if isinstance(obj, dict):
        for field in unique_fields:
            if field not in obj:
                return None
            value = obj[field]
            lookup_key.append(
                orjson.dumps(value, option=orjson.OPT_SORT_KEYS)
                if isinstance(value, (dict, list))
                else value
            )
    else:
        for field in unique_fields:
            if not hasattr(obj, field):
                return None
            value = getattr(obj, field)
            lookup_key.append(
                orjson.dumps(value, option=orjson.OPT_SORT_KEYS)
                if isinstance(value, (dict, list))
                else value
            )
    return tuple(lookup_key)


class BaseQuerySet(
    TenancyMixin,
    QuerySetPropsMixin,
    PrefetchMixin,
    QuerySetType,
):
    """Internal definitions for queryset."""

    def __init__(
        self,
        model_class: Union[type[BaseModelType], None] = None,
        *,
        database: Union[Database, None] = None,
        filter_clauses: Iterable[Any] = _empty_set,
        select_related: Iterable[str] = _empty_set,
        prefetch_related: Iterable[Prefetch] = _empty_set,
        limit_count: Optional[int] = None,
        limit: Optional[int] = None,
        limit_offset: Optional[int] = None,
        offset: Optional[int] = None,
        batch_size: Optional[int] = None,
        order_by: Iterable[str] = _empty_set,
        group_by: Iterable[str] = _empty_set,
        distinct_on: Union[None, Literal[True], Iterable[str]] = None,
        distinct: Union[None, Literal[True], Iterable[str]] = None,
        only_fields: Optional[Iterable[str]] = None,
        only: Iterable[str] = _empty_set,
        defer_fields: Optional[Sequence[str]] = None,
        defer: Iterable[str] = _empty_set,
        embed_parent: Optional[tuple[str, Union[str, str]]] = None,
        embed_parent_filters: Optional[tuple[str, str]] = None,
        using_schema: Union[str, None, Any] = Undefined,
        table: Optional[sqlalchemy.Table] = None,
        exclude_secrets: bool = False,
        extra_select: Optional[Iterable[sqlalchemy.expression.ClauseElement]] = None,
        reference_select: Optional[reference_select_type] = None,
    ) -> None:
        # Making sure for queries we use the main class and not the proxy
        # And enable the parent
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

        self._select_related = set(select_related)
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
        self.embed_parent_filters = embed_parent_filters
        self.using_schema = using_schema
        self._extra_select = list(extra_select) if extra_select is not None else []
        self._reference_select = (
            reference_select.copy() if isinstance(reference_select, dict) else {}
        )
        self._exclude_secrets = exclude_secrets
        # cache should not be cloned
        self._cache = QueryModelResultCache(attrs=self.model_class.pkcolumns)
        # is empty
        self._clear_cache(False)
        # this is not cleared, because the expression is immutable
        self._cached_select_related_expression: Optional[
            tuple[
                Any,
                dict[str, tuple[sqlalchemy.Table, type[BaseModelType]]],
            ]
        ] = None
        # initialize
        self.active_schema = self.get_schema()

        # Making sure the queryset always starts without any schema associated unless specified

        if table is not None:
            self.table = table
        if database is not None:
            self.database = database

    def _clone(self) -> QuerySet:
        """
        Return a copy of the current QuerySet that's ready for another
        operation.
        """
        queryset = self.__class__(
            self.model_class,
            database=getattr(self, "_database", None),
            filter_clauses=self.filter_clauses,
            select_related=self._select_related,
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
            embed_parent_filters=self.embed_parent_filters,
            using_schema=self.using_schema,
            table=getattr(self, "_table", None),
            exclude_secrets=self._exclude_secrets,
            reference_select=self._reference_select,
            extra_select=self._extra_select,
        )
        queryset.or_clauses.extend(self.or_clauses)
        queryset._cached_select_related_expression = self._cached_select_related_expression
        return cast("QuerySet", queryset)

    def _clear_cache(self, keep_result_cache: bool = False) -> None:
        if not keep_result_cache:
            self._cache.clear()
        self._cached_select_with_tables: Optional[
            tuple[Any, dict[str, tuple[sqlalchemy.Table, type[BaseModelType]]]]
        ] = None
        self._cache_count: Optional[int] = None
        self._cache_first: Optional[tuple[BaseModelType, BaseModelType]] = None
        self._cache_last: Optional[tuple[BaseModelType, BaseModelType]] = None
        # fetch all is in cache
        self._cache_fetch_all: bool = False

    def _build_order_by_expression(self, order_by: Any, expression: Any) -> Any:
        """Builds the order by expression"""
        expression = expression.order_by(*(self._prepare_order_by(entry) for entry in order_by))
        return expression

    def _build_group_by_expression(self, group_by: Any, expression: Any) -> Any:
        """Builds the group by expression"""
        expression = expression.group_by(*(self._prepare_order_by(entry) for entry in group_by))
        return expression

    async def build_where_clause(
        self, _: Any = None, tables_and_models: Optional[tables_and_models_type] = None
    ) -> Any:
        """Build a where clause from the filters which can be passed in a where function."""
        joins: Optional[Any] = None
        if tables_and_models is None:
            joins, tables_and_models = self._build_tables_join_from_relationship()
        # ignored args for passing build_where_clause in filter_clauses
        where_clauses: list[Any] = []
        if self.or_clauses:
            where_clauses.append(
                await clauses_mod.parse_clause_arg(
                    clauses_mod.or_(*self.or_clauses, no_select_related=True),
                    self,
                    tables_and_models,
                )
            )

        if self.filter_clauses:
            # we AND by default
            where_clauses.extend(
                await clauses_mod.parse_clause_args(self.filter_clauses, self, tables_and_models)
            )
        # for nicer unpacking
        if joins is None or len(tables_and_models) == 1:
            return clauses_mod.and_sqlalchemy(*where_clauses)
        expression = sqlalchemy.sql.select(
            *(
                getattr(tables_and_models[""][0].c, col)
                for col in tables_and_models[""][1].pkcolumns
            ),
        ).set_label_style(sqlalchemy.LABEL_STYLE_NONE)
        idtuple = sqlalchemy.tuple_(
            *(
                getattr(tables_and_models[""][0].c, col)
                for col in tables_and_models[""][1].pkcolumns
            )
        )
        expression = expression.select_from(joins)
        return idtuple.in_(
            expression.where(
                *where_clauses,
            )
        )

    def _build_select_distinct(self, distinct_on: Optional[Sequence[str]], expression: Any) -> Any:
        """Filters selects only specific fields. Leave empty to use simple distinct"""
        # using with columns is not supported by all databases
        if distinct_on:
            return expression.distinct(*map(self._prepare_fields_for_distinct, distinct_on))
        else:
            return expression.distinct()

    @classmethod
    def _join_table_helper(
        cls,
        join_clause: Any,
        current_transition: tuple[str, str, str],
        *,
        transitions: dict[tuple[str, str, str], tuple[Any, Optional[tuple[str, str, str]], str]],
        tables_and_models: dict[str, tuple[sqlalchemy.Table, type[BaseModelType]]],
    ) -> Any:
        if current_transition not in transitions:
            return join_clause
        transition_value = transitions.pop(current_transition)

        if transition_value[1] is not None:
            join_clause = cls._join_table_helper(
                join_clause,
                transition_value[1],
                transitions=transitions,
                tables_and_models=tables_and_models,
            )

        return sqlalchemy.sql.join(
            join_clause,
            tables_and_models[transition_value[2]][0],
            transition_value[0],
            isouter=True,
        )

    def _build_tables_join_from_relationship(
        self,
    ) -> tuple[Any, tables_and_models_type]:
        """
        Builds the tables relationships and joins.
        When a table contains more than one foreign key pointing to the same
        destination table, a lookup for the related field is made to understand
        from which foreign key the table is looked up from.
        """

        # How does this work?
        # First we build a transitions tree (maintable is root) by providing optionally a dependency.
        # Resolving a dependency automatically let's us resolve the tree.
        # At last we iter through the transisitions and build their dependencies first
        # We pop out the transitions so a path is not taken 2 times

        # Why left outer join? It is possible and legal for a relation to not exist we check that already in filtering.

        if self._cached_select_related_expression is None:
            maintable = self.table
            select_from = maintable
            tables_and_models: tables_and_models_type = {"": (select_from, self.model_class)}
            _select_tables_and_models: tables_and_models_type = {
                "": (select_from, self.model_class)
            }
            transitions: dict[
                tuple[str, str, str], tuple[Any, Optional[tuple[str, str, str]], str]
            ] = {}

            # Select related
            for select_path in self._select_related:
                # For m2m relationships
                model_class = self.model_class
                former_table = maintable
                former_transition = None
                prefix: str = ""
                # prefix which expands m2m fields
                _select_prefix: str = ""
                # False (default): add prefix regularly.
                # True: skip adding existing prefix to tables_and_models and skip adding the next field to the
                #       public prefix.
                # string: add a custom prefix instead of the calculated one and skip adding the next field to the
                #         public prefix.

                injected_prefix: Union[bool, str] = False
                model_database: Optional[Database] = self.database
                while select_path:
                    field_name = select_path.split("__", 1)[0]
                    try:
                        field = model_class.meta.fields[field_name]
                    except KeyError:
                        raise QuerySetError(
                            detail=f'Selected field "{field_name}" does not exist on {model_class}.'
                        ) from None
                    field = model_class.meta.fields[field_name]
                    if isinstance(field, RelationshipField):
                        model_class, reverse_part, select_path = field.traverse_field(select_path)
                    else:
                        raise QuerySetError(
                            detail=f'Selected field "{field_name}" is not a RelationshipField on {model_class}.'
                        )
                    if isinstance(field, BaseForeignKey):
                        foreign_key = field
                        reverse = False
                    else:
                        foreign_key = model_class.meta.fields[reverse_part]
                        reverse = True
                    if foreign_key.is_cross_db(model_database):
                        raise QuerySetError(
                            detail=f'Selected model "{field_name}" is on another database.'
                        )
                    # now use the one of the model_class itself
                    model_database = None
                    if injected_prefix:
                        injected_prefix = False
                    else:
                        prefix = f"{prefix}__{field_name}" if prefix else f"{field_name}"
                    _select_prefix = (
                        f"{_select_prefix}__{field_name}" if _select_prefix else f"{field_name}"
                    )
                    if foreign_key.is_m2m and foreign_key.embed_through != "":  # type: ignore
                        # we need to inject the through model for the select
                        model_class = foreign_key.through
                        if foreign_key.embed_through is False:
                            injected_prefix = True
                        else:
                            injected_prefix = f"{prefix}__{foreign_key.embed_through}"
                        if reverse:
                            select_path = f"{foreign_key.from_foreign_key}__{select_path}"
                        else:
                            select_path = f"{foreign_key.to_foreign_key}__{select_path}"
                        # if select_path is empty
                        select_path = select_path.removesuffix("__")
                        if reverse:
                            foreign_key = model_class.meta.fields[foreign_key.to_foreign_key]
                        else:
                            foreign_key = model_class.meta.fields[foreign_key.from_foreign_key]
                            reverse = True
                    if _select_prefix in _select_tables_and_models:
                        # use prexisting prefix
                        table: Any = _select_tables_and_models[_select_prefix][0]
                    else:
                        table = model_class.table_schema(self.active_schema)
                        table = table.alias(hash_tablekey(tablekey=table.key, prefix=prefix))

                    # it is guranteed that former_table is either root and has a key or is an unique join node
                    # except there would be a hash collision which is very unlikely
                    transition_key = (get_table_key_or_name(former_table), table.name, field_name)
                    if transition_key in transitions:
                        # can not provide new informations
                        former_table = table
                        former_transition = transition_key
                        continue
                    and_clause = clauses_mod.and_sqlalchemy(
                        *self._select_from_relationship_clause_generator(
                            foreign_key, table, reverse, former_table
                        )
                    )
                    transitions[transition_key] = (
                        and_clause,
                        former_transition,
                        _select_prefix,
                    )
                    if injected_prefix is False:
                        tables_and_models[prefix] = table, model_class
                    elif injected_prefix is not True:
                        # we inject a string
                        tables_and_models[injected_prefix] = table, model_class

                    # prefix used for select_related
                    _select_tables_and_models[_select_prefix] = table, model_class
                    former_table = table
                    former_transition = transition_key

            while transitions:
                select_from = self._join_table_helper(
                    select_from,
                    next(iter(transitions.keys())),
                    transitions=transitions,
                    tables_and_models=_select_tables_and_models,
                )
            self._cached_select_related_expression = (
                select_from,
                tables_and_models,
            )
        return self._cached_select_related_expression

    @staticmethod
    def _select_from_relationship_clause_generator(
        foreign_key: BaseForeignKey,
        table: Any,
        reverse: bool,
        former_table: Any,
    ) -> Any:
        column_names = foreign_key.get_column_names(foreign_key.name)
        assert column_names, f"foreign key without column names detected: {foreign_key.name}"
        for col in column_names:
            colname = foreign_key.from_fk_field_name(foreign_key.name, col) if reverse else col
            if reverse:
                yield getattr(former_table.c, colname) == getattr(table.c, col)
            else:
                yield getattr(former_table.c, colname) == getattr(
                    table.c, foreign_key.from_fk_field_name(foreign_key.name, col)
                )

    def _validate_only_and_defer(self) -> None:
        if self._only and self._defer:
            raise QuerySetError("You cannot use .only() and .defer() at the same time.")

    async def _as_select_with_tables(
        self,
    ) -> tuple[Any, tables_and_models_type]:
        """
        Builds the query select based on the given parameters and filters.
        """
        self._validate_only_and_defer()
        joins, tables_and_models = self._build_tables_join_from_relationship()
        columns_and_extra: list[Any] = [*self._extra_select]
        for prefix, (table, model_class) in tables_and_models.items():
            if not prefix:
                for column_key, column in table.columns.items():
                    # e.g. reflection has not always a field
                    field_name = model_class.meta.columns_to_field.get(column_key, column_key)
                    if self._only and field_name not in self._only:
                        continue
                    if self._defer and field_name in self._defer:
                        continue
                    if (
                        self._exclude_secrets
                        and field_name in model_class.meta.fields
                        and model_class.meta.fields[field_name].secret
                    ):
                        continue
                    # add without alias
                    columns_and_extra.append(column)

            else:
                for column_key, column in table.columns.items():
                    # e.g. reflection has not always a field
                    field_name = model_class.meta.columns_to_field.get(column_key, column_key)
                    if (
                        self._only
                        and prefix not in self._only
                        and f"{prefix}__{field_name}" not in self._only
                    ):
                        continue
                    if self._defer and (
                        prefix in self._defer or f"{prefix}__{field_name}" in self._defer
                    ):
                        continue
                    if (
                        self._exclude_secrets
                        and field_name in model_class.meta.fields
                        and model_class.meta.fields[field_name].secret
                    ):
                        continue
                    # alias has name not a key. The name is fully descriptive
                    columns_and_extra.append(column.label(f"{table.name}_{column_key}"))
        assert columns_and_extra, "no columns or extra_select specified"
        # all columns are aliased already
        expression = sqlalchemy.sql.select(*columns_and_extra).set_label_style(
            sqlalchemy.LABEL_STYLE_NONE
        )
        expression = expression.select_from(joins)
        expression = expression.where(await self.build_where_clause(self, tables_and_models))

        if self._order_by:
            expression = self._build_order_by_expression(self._order_by, expression=expression)

        if self.limit_count:
            expression = expression.limit(self.limit_count)

        if self._offset:
            expression = expression.offset(self._offset)

        if self._group_by:
            expression = self._build_group_by_expression(self._group_by, expression=expression)

        if self.distinct_on is not None:
            expression = self._build_select_distinct(self.distinct_on, expression=expression)
        return expression, tables_and_models

    async def as_select_with_tables(
        self,
    ) -> tuple[Any, tables_and_models_type]:
        """
        Builds the query select based on the given parameters and filters.
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

                # bind local vars
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
                    _op: Optional[str] = op,
                    _prefix: str = related_str,
                    # generic field has no field name
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

    def _prepare_order_by(self, order_by: str) -> Any:
        reverse = order_by.startswith("-")
        order_by = order_by.lstrip("-")
        order_col = self.table.columns[order_by]
        return order_col.desc() if reverse else order_col

    def _prepare_fields_for_distinct(self, distinct_on: str) -> sqlalchemy.Column:
        return self.table.columns[distinct_on]

    async def _embed_parent_in_result(
        self, result: Union[EdgyModel, Awaitable[EdgyModel]]
    ) -> tuple[EdgyModel, Any]:
        if isawaitable(result):
            result = await result
        if not self.embed_parent:
            return (cast(EdgyModel, result), cast(EdgyModel, result))
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
        return cast(EdgyModel, result), new_result

    async def _get_or_cache_row(
        self,
        row: Any,
        tables_and_models: dict[str, tuple[sqlalchemy.Table, type[BaseModelType]]],
        extra_attr: str = "",
        raw: bool = False,
    ) -> tuple[EdgyModel, EdgyModel]:
        is_defer_fields = bool(self._defer)
        raw_result, result = (
            await self._cache.aget_or_cache_many(
                self.model_class,
                [row],
                cache_fn=lambda _row: self.model_class.from_sqla_row(
                    _row,
                    tables_and_models=tables_and_models,
                    select_related=self._select_related,
                    only_fields=self._only,
                    is_defer_fields=is_defer_fields,
                    prefetch_related=self._prefetch_related,
                    exclude_secrets=self._exclude_secrets,
                    using_schema=self.active_schema,
                    database=self.database,
                    reference_select=self._reference_select,
                ),
                transform_fn=self._embed_parent_in_result,
            )
        )[0]
        if extra_attr:
            for attr in extra_attr.split(","):
                setattr(self, attr, result)
        return cast("EdgyModel", raw_result), cast("EdgyModel", result)

    def get_schema(self) -> Optional[str]:
        # Differs from get_schema global
        schema = self.using_schema
        if schema is Undefined:
            schema = get_schema()
        if schema is None:
            schema = self.model_class.get_db_schema()
        return schema

    async def _handle_batch(
        self,
        batch: Sequence[sqlalchemy.Row],
        tables_and_models: dict[str, tuple[sqlalchemy.Table, type[BaseModelType]]],
        queryset: BaseQuerySet,
    ) -> Sequence[tuple[BaseModelType, BaseModelType]]:
        is_defer_fields = bool(queryset._defer)
        del queryset
        _prefetch_related: list[Prefetch] = []

        for prefetch in self._prefetch_related:
            check_prefetch_collision(self.model_class, prefetch)  # type: ignore

            crawl_result = crawl_relationship(
                self.model_class, prefetch.related_name, traverse_last=True
            )
            if crawl_result.cross_db_remainder:
                raise NotImplementedError(
                    "Cannot prefetch from other db yet. Maybe in future this feature will be added."
                )
            if crawl_result.reverse_path is False:
                QuerySetError(
                    detail=("Creating a reverse path is not possible, unidirectional fields used.")
                )
            prefetch_queryset: Optional[QuerySet] = prefetch.queryset

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
                # ensure local or
                prefetch_queryset = prefetch_queryset.local_or(*clauses)

            if prefetch_queryset.model_class is self.model_class:
                # queryset is of this model
                prefetch_queryset = prefetch_queryset.select_related(prefetch.related_name)
                prefetch_queryset.embed_parent = (prefetch.related_name, "")
            else:
                # queryset is of the target model
                prefetch_queryset = prefetch_queryset.select_related(
                    cast(str, crawl_result.reverse_path)
                )
            new_prefetch = Prefetch(
                related_name=prefetch.related_name,
                to_attr=prefetch.to_attr,
                queryset=prefetch_queryset,
            )
            new_prefetch._bake_prefix = f"{hash_tablekey(tablekey=tables_and_models[''][0].key, prefix=cast(str, crawl_result.reverse_path))}_"
            new_prefetch._is_finished = True
            _prefetch_related.append(new_prefetch)

        return cast(
            Sequence[tuple[BaseModelType, BaseModelType]],
            await self._cache.aget_or_cache_many(
                self.model_class,
                batch,
                cache_fn=lambda row: self.model_class.from_sqla_row(
                    row,
                    tables_and_models=tables_and_models,
                    select_related=self._select_related,
                    only_fields=self._only,
                    is_defer_fields=is_defer_fields,
                    prefetch_related=_prefetch_related,
                    exclude_secrets=self._exclude_secrets,
                    using_schema=self.active_schema,
                    database=self.database,
                    reference_select=self._reference_select,
                ),
                transform_fn=self._embed_parent_in_result,
            ),
        )

    @property
    def _current_row(self) -> Optional[sqlalchemy.Row]:
        """Get async safe the current row when in _execute_iterate"""
        row_holder = _current_row_holder.get()
        if not row_holder:
            return None
        return row_holder[0]

    async def _execute_iterate(
        self, fetch_all_at_once: bool = False
    ) -> AsyncIterator[BaseModelType]:
        """
        Executes the query, iterate.
        """
        if self._cache_fetch_all:
            for result in cast(
                Sequence[tuple[BaseModelType, BaseModelType]],
                self._cache.get_category(self.model_class).values(),
            ):
                yield result[1]
        queryset = self
        if queryset.embed_parent:
            # activates distinct, not distinct on
            queryset = queryset.distinct()  # type: ignore

        expression, tables_and_models = await queryset.as_select_with_tables()

        if not fetch_all_at_once and bool(queryset.database.force_rollback):
            # force_rollback on db = we have only one connection
            # so every operation must be atomic
            # Note: force_rollback is a bit magic, it evaluates its truthiness to the actual value
            warnings.warn(
                'Using queryset iterations with "Database"-level force_rollback set is risky. '
                "Deadlocks can occur because only one connection is used.",
                UserWarning,
                stacklevel=3,
            )
            if queryset._prefetch_related:
                # prefetching will certainly deadlock, let's mitigate
                fetch_all_at_once = True

        counter = 0
        last_element: Optional[tuple[BaseModelType, BaseModelType]] = None
        check_db_connection(queryset.database, stacklevel=4)
        current_row: list[Optional[sqlalchemy.Row]] = [None]
        token = _current_row_holder.set(current_row)
        try:
            if fetch_all_at_once:
                async with queryset.database as database:
                    batch = cast(Sequence[sqlalchemy.Row], await database.fetch_all(expression))
                for row_num, result in enumerate(
                    await self._handle_batch(batch, tables_and_models, queryset)
                ):
                    if counter == 0:
                        self._cache_first = result
                    last_element = result
                    counter += 1
                    current_row[0] = batch[row_num]
                    yield result[1]
                self._cache_fetch_all = True
            else:
                async with queryset.database as database:
                    async for batch in cast(
                        AsyncGenerator[Sequence[sqlalchemy.Row], None],
                        database.batched_iterate(expression, batch_size=self._batch_size),
                    ):
                        # clear only result cache
                        self._cache.clear()
                        self._cache_fetch_all = False
                        for row_num, result in enumerate(
                            await self._handle_batch(batch, tables_and_models, queryset)
                        ):
                            if counter == 0:
                                self._cache_first = result
                            last_element = result
                            counter += 1
                            current_row[0] = batch[row_num]
                            yield result[1]
        finally:
            _current_row_holder.reset(token)
        # better update them once
        self._cache_count = counter
        self._cache_last = last_element

    async def _execute_all(self) -> list[EdgyModel]:
        return [result async for result in self._execute_iterate(fetch_all_at_once=True)]

    def _filter_or_exclude(
        self,
        kwargs: Any,
        clauses: Sequence[
            Union[
                sqlalchemy.sql.expression.BinaryExpression,
                Callable[
                    [QuerySetType],
                    Union[
                        sqlalchemy.sql.expression.BinaryExpression,
                        Awaitable[sqlalchemy.sql.expression.BinaryExpression],
                    ],
                ],
                dict[str, Any],
                QuerySet,
            ]
        ],
        exclude: bool = False,
        or_: bool = False,
        allow_global_or: bool = True,
    ) -> QuerySet:
        """
        Filters or excludes a given clause for a specific QuerySet.
        """
        queryset: QuerySet = self._clone()
        if kwargs:
            clauses = [*clauses, kwargs]
        converted_clauses: Sequence[
            Union[
                sqlalchemy.sql.expression.BinaryExpression,
                Callable[
                    [QuerySetType],
                    Union[
                        sqlalchemy.sql.expression.BinaryExpression,
                        Awaitable[sqlalchemy.sql.expression.BinaryExpression],
                    ],
                ],
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
                        # add to global or
                        assert not exclude
                        queryset.or_clauses.append(wrapper_and)
                        return queryset
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
                converted_clauses.append(raw_clause)
                if hasattr(raw_clause, "_edgy_calculate_select_related"):
                    select_related_calculated = raw_clause._edgy_calculate_select_related(queryset)
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
            # default to and
            queryset.filter_clauses.extend(converted_clauses)
        return queryset

    async def _model_based_delete(self) -> int:
        queryset = self.limit(self._batch_size)
        # we set embed_parent on the copy to None to get raw instances
        # embed_parent_filters is not affected
        queryset.embed_parent = None
        counter = 0
        models = await queryset
        while models:
            for model in models:
                counter += 1
                # delete issues already signals
                await model.delete()
            # clear cache and fetch new batch
            models = await queryset.all(True)
        self._clear_cache()
        return counter

    async def _get_raw(self, **kwargs: Any) -> tuple[BaseModelType, Any]:
        """
        Returns a single record based on the given kwargs.
        """

        if kwargs:
            cached = cast(
                Optional[tuple[BaseModelType, Any]], self._cache.get(self.model_class, kwargs)
            )
            if cached is not None:
                return cached
            filter_query = cast("BaseQuerySet", self.filter(**kwargs))
            # connect parent query cache
            filter_query._cache = self._cache
            return await filter_query._get_raw()

        expression, tables_and_models = await self.as_select_with_tables()
        check_db_connection(self.database, stacklevel=4)
        async with self.database as database:
            # we want no queryset copy, so use sqlalchemy limit(2)
            rows = await database.fetch_all(expression.limit(2))

        if not rows:
            self._cache_count = 0
            raise ObjectNotFound()
        if len(rows) > 1:
            raise MultipleObjectsReturned()
        self._cache_count = 1

        return await self._get_or_cache_row(rows[0], tables_and_models, "_cache_first,_cache_last")

    def __repr__(self) -> str:
        return f"QuerySet<{self.sql}>"


class QuerySet(BaseQuerySet):
    """
    QuerySet object used for query retrieving. Public interface
    """

    async def _sql_helper(self) -> Any:
        async with self.database:
            return (await self.as_select()).compile(
                self.database.engine, compile_kwargs={"literal_binds": True}
            )

    @cached_property
    def sql(self) -> str:
        """Get SQL select query as string with inserted blanks. For debugging only!"""
        return str(run_sync(self._sql_helper()))

    def filter(
        self,
        *clauses: Union[
            sqlalchemy.sql.expression.BinaryExpression,
            Callable[
                [QuerySetType],
                Union[
                    sqlalchemy.sql.expression.BinaryExpression,
                    Awaitable[sqlalchemy.sql.expression.BinaryExpression],
                ],
            ],
            dict[str, Any],
            QuerySet,
        ],
        **kwargs: Any,
    ) -> QuerySet:
        """
        Filters the QuerySet by the given kwargs and clauses.
        """
        return self._filter_or_exclude(clauses=clauses, kwargs=kwargs)

    def all(self, clear_cache: bool = False) -> QuerySet:
        """
        Returns a cloned query with empty cache. Optionally just clear the cache and return the same query.
        """
        if clear_cache:
            self._clear_cache()
            return self
        return self._clone()

    def or_(
        self,
        *clauses: Union[
            sqlalchemy.sql.expression.BinaryExpression,
            Callable[
                [QuerySetType],
                Union[
                    sqlalchemy.sql.expression.BinaryExpression,
                    Awaitable[sqlalchemy.sql.expression.BinaryExpression],
                ],
            ],
            dict[str, Any],
            QuerySet,
        ],
        **kwargs: Any,
    ) -> QuerySet:
        """
        Filters the QuerySet by the OR operand.
        """
        return self._filter_or_exclude(clauses=clauses, or_=True, kwargs=kwargs)

    def local_or(
        self,
        *clauses: Union[
            sqlalchemy.sql.expression.BinaryExpression,
            Callable[
                [QuerySetType],
                Union[
                    sqlalchemy.sql.expression.BinaryExpression,
                    Awaitable[sqlalchemy.sql.expression.BinaryExpression],
                ],
            ],
            dict[str, Any],
            QuerySet,
        ],
        **kwargs: Any,
    ) -> QuerySet:
        """
        Filters the QuerySet by the OR operand.
        """
        return self._filter_or_exclude(
            clauses=clauses, or_=True, kwargs=kwargs, allow_global_or=False
        )

    def and_(
        self,
        *clauses: Union[
            sqlalchemy.sql.expression.BinaryExpression,
            Callable[
                [QuerySetType],
                Union[
                    sqlalchemy.sql.expression.BinaryExpression,
                    Awaitable[sqlalchemy.sql.expression.BinaryExpression],
                ],
            ],
            dict[str, Any],
        ],
        **kwargs: Any,
    ) -> QuerySet:
        """
        Filters the QuerySet by the AND operand. Alias of filter.
        """
        return self._filter_or_exclude(clauses=clauses, kwargs=kwargs)

    def not_(
        self,
        *clauses: Union[
            sqlalchemy.sql.expression.BinaryExpression,
            Callable[
                [QuerySetType],
                Union[
                    sqlalchemy.sql.expression.BinaryExpression,
                    Awaitable[sqlalchemy.sql.expression.BinaryExpression],
                ],
            ],
            dict[str, Any],
            QuerySet,
        ],
        **kwargs: Any,
    ) -> QuerySet:
        """
        Filters the QuerySet by the NOT operand. Alias of exclude.
        """
        return self.exclude(*clauses, **kwargs)

    def exclude(
        self,
        *clauses: Union[
            sqlalchemy.sql.expression.BinaryExpression,
            Callable[
                [QuerySetType],
                Union[
                    sqlalchemy.sql.expression.BinaryExpression,
                    Awaitable[sqlalchemy.sql.expression.BinaryExpression],
                ],
            ],
            dict[str, Any],
            QuerySet,
        ],
        **kwargs: Any,
    ) -> QuerySet:
        """
        Exactly the same as the filter but for the exclude.
        """
        return self._filter_or_exclude(clauses=clauses, exclude=True, kwargs=kwargs)

    def exclude_secrets(
        self,
        exclude_secrets: bool = True,
    ) -> QuerySet:
        """
        Excludes any field that contains the `secret=True` declared from being leaked.
        """
        queryset = self._clone()
        queryset._exclude_secrets = exclude_secrets
        return queryset

    def extra_select(
        self,
        *extra: sqlalchemy.expression.ColumnClause,
    ) -> QuerySetType:
        queryset = self._clone()
        queryset._extra_select.extend(extra)
        return queryset

    def reference_select(self, references: reference_select_type) -> QuerySetType:
        queryset = self._clone()
        queryset._reference_select.update(references)
        return queryset

    def batch_size(
        self,
        batch_size: Optional[int] = None,
    ) -> QuerySet:
        """
        Set batch/chunk size. Used for iterate
        """
        queryset = self._clone()
        queryset._batch_size = batch_size
        return queryset

    def lookup(self, term: Any) -> QuerySet:
        """
        Broader way of searching for a given term
        """
        queryset: QuerySet = self._clone()
        if not term:
            return queryset

        filter_clauses = list(queryset.filter_clauses)
        value = f"%{term}%"

        search_fields = [
            name
            for name, field in queryset.model_class.meta.fields.items()
            if isinstance(field, (CharField, TextField))
        ]
        search_clauses = [queryset.table.columns[name].ilike(value) for name in search_fields]

        if len(search_clauses) > 1:
            filter_clauses.append(sqlalchemy.sql.or_(*search_clauses))
        else:
            filter_clauses.extend(search_clauses)

        return queryset

    def order_by(self, *order_by: str) -> QuerySet:
        """
        Returns a QuerySet ordered by the given fields.
        """
        queryset: QuerySet = self._clone()
        queryset._order_by = order_by
        return queryset

    def reverse(self) -> QuerySet:
        if not self._order_by:
            queryset = self.order_by(*self.model_class.pkcolumns)
        else:
            queryset = self._clone()
        queryset._order_by = tuple(
            el[1:] if el.startswith("-") else f"-{el}" for el in queryset._order_by
        )
        queryset._cache_last = self._cache_first
        queryset._cache_first = self._cache_last
        queryset._cache_count = self._cache_count
        if self._cache_fetch_all:
            queryset._cache.update(
                list(reversed(self._cache.get_category(self.model_class).values()))
            )
            queryset._cache_fetch_all = True
        return queryset

    def limit(self, limit_count: int) -> QuerySet:
        """
        Returns a QuerySet limited by.
        """
        queryset: QuerySet = self._clone()
        queryset.limit_count = limit_count
        return queryset

    def offset(self, offset: int) -> QuerySet:
        """
        Returns a Queryset limited by the offset.
        """
        queryset: QuerySet = self._clone()
        queryset._offset = offset
        return queryset

    def group_by(self, *group_by: str) -> QuerySet:
        """
        Returns the values grouped by the given fields.
        """
        queryset: QuerySet = self._clone()
        queryset._group_by = group_by
        return queryset

    def distinct(self, first: Union[bool, str] = True, *distinct_on: str) -> QuerySet:
        """
        Returns a queryset with distinct results.
        """
        queryset: QuerySet = self._clone()
        if first is False:
            queryset.distinct_on = None
        elif first is True:
            queryset.distinct_on = []
        else:
            queryset.distinct_on = [first, *distinct_on]
        return queryset

    def only(self, *fields: str) -> QuerySet:
        """
        Returns a list of models with the selected only fields and always the primary
        key.
        """
        queryset: QuerySet = self._clone()
        only_fields = set(fields)
        if self.model_class.pknames:
            for pkname in self.model_class.pknames:
                if pkname not in fields:
                    for pkcolumn in self.model_class.meta.get_columns_for_name(pkname):
                        only_fields.add(pkcolumn.key)
        else:
            for pkcolumn in self.model_class.pkcolumns:
                only_fields.add(pkcolumn.key)
        queryset._only = only_fields
        return queryset

    def defer(self, *fields: str) -> QuerySet:
        """
        Returns a list of models with the selected only fields and always the primary
        key.
        """
        queryset: QuerySet = self._clone()

        queryset._defer = set(fields)
        return queryset

    def select_related(self, *related: str) -> QuerySet:
        """
        Returns a QuerySet that will “follow” foreign-key relationships, selecting additional
        related-object data when it executes its query.

        This is a performance booster which results in a single more complex query but means

        later use of foreign-key relationships won't require database queries.
        """
        queryset: QuerySet = self._clone()
        if len(related) >= 1 and not isinstance(cast(Any, related[0]), str):
            warnings.warn(
                "use `select_related` with variadic str arguments instead of a Sequence",
                DeprecationWarning,
                stacklevel=2,
            )
            related = cast(tuple[str, ...], related[0])
        if not self._select_related.issuperset(related):
            queryset._cached_select_related_expression = None
            queryset._select_related.update(related)
        return queryset

    async def values(
        self,
        fields: Union[Sequence[str], str, None] = None,
        exclude: Union[Sequence[str], set[str]] = None,
        exclude_none: bool = False,
    ) -> list[Any]:
        """
        Returns the results in a python dictionary format.
        """

        if isinstance(fields, str):
            fields = [fields]

        rows: list[BaseModelType] = await self

        if fields is not None and not isinstance(fields, Iterable):
            raise QuerySetError(detail="Fields must be a suitable sequence of strings or unset.")

        if not fields:
            rows = [row.model_dump(exclude=exclude, exclude_none=exclude_none) for row in rows]
        else:
            rows = [
                row.model_dump(exclude=exclude, exclude_none=exclude_none, include=fields)
                for row in rows
            ]
        return rows

    async def values_list(
        self,
        fields: Union[Sequence[str], str, None] = None,
        exclude: Union[Sequence[str], set[str]] = None,
        exclude_none: bool = False,
        flat: bool = False,
    ) -> list[Any]:
        """
        Returns the results in a python dictionary format.
        """
        rows = await self.values(
            fields=fields,
            exclude=exclude,
            exclude_none=exclude_none,
        )
        if not flat:
            return [tuple(row.values()) for row in rows]
        else:
            try:
                return [row[fields[0]] for row in rows]
            except KeyError:
                raise QuerySetError(detail=f"{fields[0]} does not exist in the results.") from None

    async def exists(self, **kwargs: Any) -> bool:
        """
        Returns a boolean indicating if a record exists or not.
        """
        if kwargs:
            # check cache for existance
            cached = self._cache.get(self.model_class, kwargs)
            if cached is not None:
                return True
            filter_query = self.filter(**kwargs)
            filter_query._cache = self._cache
            return await filter_query.exists()
        queryset: QuerySet = self
        expression = (await queryset.as_select()).exists().select()
        check_db_connection(queryset.database)
        async with queryset.database as database:
            _exists = await database.fetch_val(expression)
        return cast(bool, _exists)

    async def count(self) -> int:
        """
        Returns an indicating the total records.
        """
        if self._cache_count is not None:
            return self._cache_count
        queryset: QuerySet = self
        expression = (await queryset.as_select()).alias("subquery_for_count")
        expression = sqlalchemy.func.count().select().select_from(expression)
        check_db_connection(queryset.database)
        async with queryset.database as database:
            self._cache_count = count = cast("int", await database.fetch_val(expression))
        return count

    async def get_or_none(self, **kwargs: Any) -> Union[EdgyEmbedTarget, None]:
        """
        Fetch one object matching the parameters or returns None.
        """
        try:
            return await self.get(**kwargs)
        except ObjectNotFound:
            return None

    async def get(self, **kwargs: Any) -> EdgyEmbedTarget:
        """
        Returns a single record based on the given kwargs.
        """
        return cast(EdgyEmbedTarget, (await self._get_raw(**kwargs))[1])

    async def first(self) -> Union[EdgyEmbedTarget, None]:
        """
        Returns the first record of a given queryset.
        """
        if self._cache_count is not None and self._cache_count == 0:
            return None
        if self._cache_first is not None:
            return cast(EdgyEmbedTarget, self._cache_first[1])
        queryset = self
        if not queryset._order_by:
            queryset = queryset.order_by(*self.model_class.pkcolumns)
        expression, tables_and_models = await queryset.as_select_with_tables()
        self._cached_select_related_expression = queryset._cached_select_related_expression
        check_db_connection(queryset.database)
        async with queryset.database as database:
            row = await database.fetch_one(expression, pos=0)
        if row:
            return (
                await self._get_or_cache_row(row, tables_and_models, extra_attr="_cache_first")
            )[1]
        return None

    async def last(self) -> Union[EdgyEmbedTarget, None]:
        """
        Returns the last record of a given queryset.
        """
        if self._cache_count is not None and self._cache_count == 0:
            return None
        if self._cache_last is not None:
            return cast(EdgyEmbedTarget, self._cache_last[1])
        queryset = self
        if not queryset._order_by:
            queryset = queryset.order_by(*self.model_class.pkcolumns)
        queryset = queryset.reverse()
        expression, tables_and_models = await queryset.as_select_with_tables()
        self._cached_select_related_expression = queryset._cached_select_related_expression
        check_db_connection(queryset.database)
        async with queryset.database as database:
            row = await database.fetch_one(expression, pos=0)
        if row:
            return (
                await self._get_or_cache_row(row, tables_and_models, extra_attr="_cache_last")
            )[1]
        return None

    async def create(self, *args: Any, **kwargs: Any) -> EdgyEmbedTarget:
        """
        Creates a record in a specific table.
        """
        # for tenancy
        queryset: QuerySet = self._clone()
        check_db_connection(queryset.database)
        token = CHECK_DB_CONNECTION_SILENCED.set(True)
        try:
            instance = queryset.model_class(*args, **kwargs)
            apply_instance_extras(
                instance,
                self.model_class,
                schema=self.using_schema,
                table=queryset.table,
                database=queryset.database,
            )
            # values=set(kwargs.keys()) is required for marking the provided kwargs as explicit provided kwargs
            instance = await instance.save(force_insert=True, values=set(kwargs.keys()))
            result = await self._embed_parent_in_result(instance)
            self._clear_cache(True)
            self._cache.update([result])
            return cast(EdgyEmbedTarget, result[1])
        finally:
            CHECK_DB_CONNECTION_SILENCED.reset(token)

    async def bulk_create(self, objs: Iterable[Union[dict[str, Any], EdgyModel]]) -> None:
        """
        Bulk creates records in a table
        """
        queryset: QuerySet = self._clone()

        new_objs: list[EdgyModel] = []

        async def _iterate(obj_or_dict: Union[EdgyModel, dict[str, Any]]) -> dict[str, Any]:
            if isinstance(obj_or_dict, dict):
                obj: EdgyModel = queryset.model_class(**obj_or_dict)
                if (
                    self.model_class.meta.post_save_fields
                    and not self.model_class.meta.post_save_fields.isdisjoint(obj_or_dict.keys())
                ):
                    new_objs.append(obj)
            else:
                obj = obj_or_dict
                if self.model_class.meta.post_save_fields:
                    new_objs.append(obj)
            original = obj.extract_db_fields()
            col_values: dict[str, Any] = obj.extract_column_values(
                original, phase="prepare_insert", instance=self
            )
            col_values.update(
                await obj.execute_pre_save_hooks(col_values, original, force_insert=True)
            )
            return col_values

        check_db_connection(queryset.database)
        token = CURRENT_INSTANCE.set(self)
        try:
            async with queryset.database as database, database.transaction():
                expression = queryset.table.insert().values([await _iterate(obj) for obj in objs])
                await database.execute_many(expression)
            self._clear_cache(True)
            if new_objs:
                for obj in new_objs:
                    await obj.execute_post_save_hooks(
                        self.model_class.meta.fields.keys(), force_insert=True
                    )
        finally:
            CURRENT_INSTANCE.reset(token)

    async def bulk_update(self, objs: list[EdgyModel], fields: list[str]) -> None:
        """
        Bulk updates records in a table.

        A similar solution was suggested here: https://github.com/encode/orm/pull/148

        It is thought to be a clean approach to a simple problem so it was added here and
        refactored to be compatible with Edgy.
        """
        queryset: QuerySet = self._clone()
        fields = list(fields)

        pk_query_placeholder = (
            getattr(queryset.table.c, pkcol)
            == sqlalchemy.bindparam(
                "__id" if pkcol == "id" else pkcol, type_=getattr(queryset.table.c, pkcol).type
            )
            for pkcol in queryset.pkcolumns
        )
        expression = queryset.table.update().where(*pk_query_placeholder)

        update_list = []
        fields_plus_pk = {*fields, *queryset.model_class.pkcolumns}
        check_db_connection(queryset.database)
        token = CURRENT_INSTANCE.set(self)
        try:
            async with queryset.database as database, database.transaction():
                for obj in objs:
                    extracted = obj.extract_db_fields(fields_plus_pk)
                    update = queryset.model_class.extract_column_values(
                        extracted,
                        is_update=True,
                        is_partial=True,
                        phase="prepare_update",
                        instance=self,
                        model_instance=obj,
                    )
                    update.update(
                        await obj.execute_pre_save_hooks(update, extracted, force_insert=False)
                    )
                    if "id" in update:
                        update["__id"] = update.pop("id")
                    update_list.append(update)

                values_placeholder: Any = {
                    pkcol: sqlalchemy.bindparam(pkcol, type_=getattr(queryset.table.c, pkcol).type)
                    for field in fields
                    for pkcol in queryset.model_class.meta.field_to_column_names[field]
                }
                expression = expression.values(values_placeholder)
                await database.execute_many(expression, update_list)
            self._clear_cache()
            if (
                self.model_class.meta.post_save_fields
                and not self.model_class.meta.post_save_fields.isdisjoint(fields)
            ):
                for obj in objs:
                    await obj.execute_post_save_hooks(fields, force_insert=False)
        finally:
            CURRENT_INSTANCE.reset(token)

    async def bulk_get_or_create(
        self,
        objs: list[Union[dict[str, Any], EdgyModel]],
        unique_fields: Union[list[str], None] = None,
    ) -> list[EdgyModel]:
        """
        Bulk gets or creates records in a table.

        If records exist based on unique fields, they are retrieved.
        Otherwise, new records are created.

        Args:
            objs (list[Union[dict[str, Any], EdgyModel]]): A list of objects or dictionaries.
            unique_fields (list[str] | None): Fields that determine uniqueness. If None, all records are treated as new.

        Returns:
            list[EdgyModel]: A list of retrieved or newly created objects.
        """
        queryset: QuerySet = self._clone()
        new_objs: list[EdgyModel] = []
        retrieved_objs: list[EdgyModel] = []
        check_db_connection(queryset.database)

        if unique_fields:
            existing_records: dict[tuple, EdgyModel] = {}
            for obj in objs:
                filter_kwargs = {}
                dict_fields = {}
                if isinstance(obj, dict):
                    for field in unique_fields:
                        if field in obj:
                            value = obj[field]
                            if isinstance(value, dict):
                                dict_fields[field] = value
                            else:
                                filter_kwargs[field] = value
                else:
                    for field in unique_fields:
                        value = getattr(obj, field)
                        if isinstance(value, dict):
                            dict_fields[field] = value
                        else:
                            filter_kwargs[field] = value
                lookup_key = _extract_unique_lookup_key(obj, unique_fields)
                if lookup_key is not None and lookup_key in existing_records:
                    continue
                found = False
                if bool(queryset.database.force_rollback):
                    for record in await queryset.filter(**filter_kwargs):
                        if all(
                            getattr(record, k) == expected for k, expected in dict_fields.items()
                        ):
                            lookup_key = _extract_unique_lookup_key(record, unique_fields)
                            assert lookup_key is not None, (
                                "invalid fields/attributes in unique_fields"
                            )
                            if lookup_key not in existing_records:
                                existing_records[lookup_key] = record
                            found = True
                            break
                else:
                    async for record in queryset.filter(**filter_kwargs):
                        if all(
                            getattr(record, k) == expected for k, expected in dict_fields.items()
                        ):
                            lookup_key = _extract_unique_lookup_key(record, unique_fields)
                            assert lookup_key is not None, (
                                "invalid fields/attributes in unique_fields"
                            )
                            if lookup_key not in existing_records:
                                existing_records[lookup_key] = record
                            found = True
                            break
                if found is False:
                    new_objs.append(queryset.model_class(**obj) if isinstance(obj, dict) else obj)

            retrieved_objs.extend(existing_records.values())
        else:
            new_objs.extend(
                [queryset.model_class(**obj) if isinstance(obj, dict) else obj for obj in objs]
            )

        async def _iterate(obj: EdgyModel) -> dict[str, Any]:
            original = obj.extract_db_fields()
            col_values: dict[str, Any] = obj.extract_column_values(
                original, phase="prepare_insert", instance=self
            )
            col_values.update(
                await obj.execute_pre_save_hooks(col_values, original, force_insert=True)
            )
            return col_values

        token = CURRENT_INSTANCE.set(self)

        try:
            async with queryset.database as database, database.transaction():
                if new_objs:
                    new_obj_values = [await _iterate(obj) for obj in new_objs]
                    expression = queryset.table.insert().values(new_obj_values)
                    await database.execute_many(expression)
                    retrieved_objs.extend(new_objs)

                self._clear_cache()
                for obj in new_objs:
                    await obj.execute_post_save_hooks(
                        self.model_class.meta.fields.keys(), force_insert=True
                    )
        finally:
            CURRENT_INSTANCE.reset(token)

        return retrieved_objs

    async def delete(self, use_models: bool = False) -> int:
        if (
            self.model_class.__require_model_based_deletion__
            or self.model_class.meta.post_delete_fields
        ):
            use_models = True
        if use_models:
            return await self._model_based_delete()

        # delete of model issues already signals, so don't integrate them
        await self.model_class.meta.signals.pre_delete.send_async(self.model_class, instance=self)

        expression = self.table.delete()
        expression = expression.where(await self.build_where_clause())

        check_db_connection(self.database)
        async with self.database as database:
            row_count = cast(int, await database.execute(expression))

        # clear cache before executing post_delete. Fresh results can be retrieved in signals
        self._clear_cache()

        await self.model_class.meta.signals.post_delete.send_async(
            self.model_class, instance=self, row_count=row_count
        )
        return row_count

    async def update(self, **kwargs: Any) -> None:
        """
        Updates records in a specific table with the given kwargs.

        Warning: does not execute pre_save_callback/post_save_callback hooks and passes values directly to clean.
        """

        column_values = self.model_class.extract_column_values(
            kwargs, is_update=True, is_partial=True, phase="prepare_update", instance=self
        )

        # Broadcast the initial update details
        # add is_update to match save
        await self.model_class.meta.signals.pre_update.send_async(
            self.model_class,
            instance=self,
            values=kwargs,
            column_values=column_values,
            is_update=True,
            is_migration=False,
        )

        expression = self.table.update().values(**column_values)
        expression = expression.where(await self.build_where_clause())
        check_db_connection(self.database)
        async with self.database as database:
            await database.execute(expression)

        # Broadcast the update executed
        # add is_update to match save
        await self.model_class.meta.signals.post_update.send_async(
            self.model_class,
            instance=self,
            values=kwargs,
            column_values=column_values,
            is_update=True,
            is_migration=False,
        )
        self._clear_cache()

    async def get_or_create(
        self, defaults: Union[dict[str, Any], Any, None] = None, *args: Any, **kwargs: Any
    ) -> tuple[EdgyEmbedTarget, bool]:
        """
        Creates a record in a specific table or updates if already exists.
        """
        if not isinstance(defaults, dict):
            # can be a ModelRef so pass it
            args = (defaults, *args)
            defaults = {}

        try:
            raw_instance, get_instance = await self._get_raw(**kwargs)
        except ObjectNotFound:
            kwargs.update(defaults)
            instance: EdgyEmbedTarget = await self.create(*args, **kwargs)
            return instance, True
        for arg in args:
            if isinstance(arg, ModelRef):
                relation_field = self.model_class.meta.fields[arg.__related_name__]
                extra_params = {}
                try:
                    # m2m or foreign key
                    target_model_class = relation_field.target
                except AttributeError:
                    # reverse m2m or foreign key
                    target_model_class = relation_field.related_from
                if not relation_field.is_m2m:
                    # sometimes the foreign key is required, so set it already
                    extra_params[relation_field.foreign_key.name] = raw_instance
                model = target_model_class(
                    **arg.model_dump(exclude={"__related_name__"}),
                    **extra_params,
                )
                relation = getattr(raw_instance, arg.__related_name__)
                await relation.add(model)
        return cast(EdgyEmbedTarget, get_instance), False

    async def update_or_create(
        self, defaults: Union[dict[str, Any], Any, None] = None, *args: Any, **kwargs: Any
    ) -> tuple[EdgyEmbedTarget, bool]:
        """
        Updates a record in a specific table or creates a new one.
        """
        if not isinstance(defaults, dict):
            # can be a ModelRef so pass it
            args = (defaults, *args)
            defaults = {}
        try:
            raw_instance, get_instance = await self._get_raw(**kwargs)
        except ObjectNotFound:
            kwargs.update(defaults)
            instance: EdgyEmbedTarget = await self.create(*args, **kwargs)
            return instance, True
        await get_instance.update(**defaults)
        for arg in args:
            if isinstance(arg, ModelRef):
                relation_field = self.model_class.meta.fields[arg.__related_name__]
                extra_params = {}
                try:
                    # m2m or foreign key
                    target_model_class = relation_field.target
                except AttributeError:
                    # reverse m2m or foreign key
                    target_model_class = relation_field.related_from
                if not relation_field.is_m2m:
                    # sometimes the foreign key is required, so set it already
                    extra_params[relation_field.foreign_key.name] = raw_instance
                model = target_model_class(
                    **arg.model_dump(exclude={"__related_name__"}),
                    **extra_params,
                )
                relation = getattr(raw_instance, arg.__related_name__)
                await relation.add(model)
        self._clear_cache()
        return cast(EdgyEmbedTarget, get_instance), False

    async def contains(self, instance: BaseModelType) -> bool:
        """Returns true if the QuerySet contains the provided object.
        False if otherwise.
        """
        query: Any = {}
        try:
            pkcolumns = instance.pkcolumns
            for pkcolumn in pkcolumns:
                query[pkcolumn] = getattr(instance, pkcolumn)
                if query[pkcolumn] is None:
                    raise ValueError("'obj' has incomplete/missing primary key.") from None
        except AttributeError:
            raise ValueError("'obj' must be a model or reflect model instance.") from None
        return await self.exists(**query)

    def transaction(self, *, force_rollback: bool = False, **kwargs: Any) -> Transaction:
        """Return database transaction for the assigned database."""
        return self.database.transaction(force_rollback=force_rollback, **kwargs)

    def __await__(
        self,
    ) -> Generator[Any, None, list[Any]]:
        return self._execute_all().__await__()

    async def __aiter__(self) -> AsyncIterator[Any]:
        async for value in self._execute_iterate():
            yield value
