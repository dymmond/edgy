import asyncio
import copy
import warnings
from collections.abc import AsyncIterator, Awaitable, Generator, Iterable, Sequence
from collections.abc import Iterable as CollectionsIterable
from functools import cached_property
from inspect import isawaitable
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Optional,
    Union,
    cast,
)

import sqlalchemy

from edgy.core.db.context_vars import CURRENT_INSTANCE, MODEL_GETATTR_BEHAVIOR, get_schema
from edgy.core.db.datastructures import QueryModelResultCache
from edgy.core.db.fields import CharField, TextField
from edgy.core.db.fields.base import BaseField, BaseForeignKey, RelationshipField
from edgy.core.db.models.model_reference import ModelRef
from edgy.core.db.models.types import BaseModelType
from edgy.core.db.models.utils import apply_instance_extras
from edgy.core.db.querysets.mixins import QuerySetPropsMixin, TenancyMixin
from edgy.core.db.querysets.prefetch import Prefetch, PrefetchMixin, check_prefetch_collision
from edgy.core.db.querysets.types import EdgyEmbedTarget, EdgyModel, QueryType
from edgy.core.db.relationships.utils import crawl_relationship
from edgy.core.utils.db import check_db_connection
from edgy.core.utils.sync import run_sync
from edgy.exceptions import MultipleObjectsReturned, ObjectNotFound, QuerySetError
from edgy.types import Undefined

from . import clauses as clauses_mod

if TYPE_CHECKING:  # pragma: no cover
    from databasez.core.transaction import Transaction

    from edgy.core.connection import Database
    from edgy.core.db.fields.types import BaseFieldType


generic_field = BaseField()


def clean_query_kwargs(
    model_class: type[BaseModelType],
    kwargs: dict[str, Any],
    embed_parent: Optional[tuple[str, str]] = None,
    model_database: Optional["Database"] = None,
) -> dict[str, Any]:
    new_kwargs: dict[str, Any] = {}
    for key, val in kwargs.items():
        if embed_parent:
            if embed_parent[1] and key.startswith(embed_parent[1]):
                key = key.removeprefix(embed_parent[1]).removeprefix("__")
            else:
                key = f"{embed_parent[0]}__{key}"
        sub_model_class, field_name, _, _, _, cross_db_remainder = crawl_relationship(
            model_class, key, model_database=model_database
        )
        # we preserve the uncleaned argument
        field = None if cross_db_remainder else sub_model_class.meta.fields.get(field_name)
        if field is not None and not callable(val):
            new_kwargs.update(field.clean(key, val, for_query=True))
        else:
            new_kwargs[key] = val
    assert "pk" not in new_kwargs, "pk should be already parsed"
    return new_kwargs


async def _parse_clause_arg(arg: Any, instance: "BaseQuerySet") -> Any:
    if callable(arg):
        arg = arg(instance)
    if isawaitable(arg):
        arg = await arg
    return arg


class BaseQuerySet(
    TenancyMixin,
    QuerySetPropsMixin,
    PrefetchMixin,
    QueryType,
):
    """Internal definitions for queryset."""

    def __init__(
        self,
        model_class: Union[type[BaseModelType], None] = None,
        database: Union["Database", None] = None,
        filter_clauses: Any = None,
        or_clauses: Any = None,
        select_related: Any = None,
        prefetch_related: Any = None,
        limit_count: Any = None,
        limit_offset: Any = None,
        batch_size: Optional[int] = None,
        order_by: Any = None,
        group_by: Any = None,
        distinct_on: Optional[Sequence[str]] = None,
        only_fields: Any = None,
        defer_fields: Any = None,
        embed_parent: Any = None,
        embed_parent_filters: Any = None,
        embed_sqla_row: str = "",
        using_schema: Any = Undefined,
        table: Any = None,
        exclude_secrets: bool = False,
    ) -> None:
        super().__init__(model_class=model_class)
        self.filter_clauses = [] if filter_clauses is None else filter_clauses
        self.or_clauses = [] if or_clauses is None else or_clauses
        self.limit_count = limit_count
        self._select_related = [] if select_related is None else select_related
        self._prefetch_related = [] if prefetch_related is None else prefetch_related
        self._offset = limit_offset
        self._batch_size = batch_size
        self._order_by = [] if order_by is None else order_by
        self._group_by = [] if group_by is None else group_by
        self.distinct_on = distinct_on
        self._only = [] if only_fields is None else only_fields
        self._defer = [] if defer_fields is None else defer_fields
        self.embed_parent = embed_parent
        self.using_schema = using_schema
        self.embed_parent_filters = embed_parent_filters
        self._exclude_secrets = exclude_secrets
        # cache should not be cloned
        self._cache = QueryModelResultCache(attrs=self.model_class.pkcolumns)
        # is empty
        self._clear_cache(False)
        # initialize
        self.active_schema = self.get_schema()

        # Making sure the queryset always starts without any schema associated unless specified

        if table is not None:
            self.table = table
        if database is not None:
            self.database = database

    def _build_order_by_expression(self, order_by: Any, expression: Any) -> Any:
        """Builds the order by expression"""
        order_by = list(map(self._prepare_order_by, order_by))
        expression = expression.order_by(*order_by)
        return expression

    def _build_group_by_expression(self, group_by: Any, expression: Any) -> Any:
        """Builds the group by expression"""
        group_by = list(map(self._prepare_group_by, group_by))
        expression = expression.group_by(*group_by)
        return expression

    async def _resolve_clause_args(self, args: Any) -> Any:
        result: list[Any] = []
        for arg in args:
            result.append(_parse_clause_arg(arg, self))
        if self.database.force_rollback:
            return [await el for el in result]
        else:
            return await asyncio.gather(*result)

    async def build_where_clause(self) -> Any:
        """Build a where clause from the filters which can be passed in a where function."""
        build_where_clause: list[Any] = []

        if self.or_clauses:
            or_clauses = await self._resolve_clause_args(self.or_clauses)
            build_where_clause.append(
                or_clauses[0] if len(or_clauses) == 1 else clauses_mod.or_(*or_clauses)
            )

        if self.filter_clauses:
            # we AND by default
            build_where_clause.extend(await self._resolve_clause_args(self.filter_clauses))
        # this simplifies the integration.
        # otherwise unrolling is required which needs extra wrapping with async functions
        return clauses_mod.and_(*build_where_clause)

    def _build_select_distinct(self, distinct_on: Optional[Sequence[str]], expression: Any) -> Any:
        """Filters selects only specific fields. Leave empty to use simple distinct"""
        # using with columns is not supported by all databases
        if distinct_on:
            return expression.distinct(*map(self._prepare_fields_for_distinct, distinct_on))
        else:
            return expression.distinct()

    def _build_tables_select_from_relationship(self) -> Any:
        """
        Builds the tables relationships and joins.
        When a table contains more than one foreign key pointing to the same
        destination table, a lookup for the related field is made to understand
        from which foreign key the table is looked up from.
        """
        queryset: QuerySet = self._clone()

        select_from = queryset.table
        tables = {select_from.name: select_from}

        # Select related
        for select_path in queryset._select_related:
            # For m2m relationships
            model_class = queryset.model_class
            former_table = queryset.table
            model_database: Optional[Database] = queryset.database
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
                table = model_class.table_schema(self.active_schema)
                if table.name not in tables:
                    select_from = sqlalchemy.sql.join(  # type: ignore
                        select_from,
                        table,
                        *self._select_from_relationship_clause_generator(
                            foreign_key, table, reverse, former_table
                        ),
                    )
                    tables[table.name] = table
                former_table = table

        return tables.values(), select_from

    @staticmethod
    def _select_from_relationship_clause_generator(
        foreign_key: BaseForeignKey,
        table: Any,
        reverse: bool,
        former_table: Any,
    ) -> Any:
        column_names = foreign_key.get_column_names(foreign_key.name)
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

    def _secret_recursive_names(
        self, model_class: Any, columns: Union[list[str], None] = None
    ) -> list[str]:
        """
        Recursively gets the names of the fields excluding the secrets.
        """
        if columns is None:
            columns = []

        for name, field in model_class.meta.fields.items():
            if field.secret:
                continue
            columns.extend(field.get_column_names(name))
            if isinstance(field, BaseForeignKey):
                # Making sure the foreign key is always added unless is a secret
                columns.extend(
                    self._secret_recursive_names(model_class=field.target, columns=columns)
                )

        columns = list(set(columns))
        return columns

    async def _build_select(self) -> Any:
        """
        Builds the query select based on the given parameters and filters.
        """
        queryset: BaseQuerySet = self

        queryset._validate_only_and_defer()
        tables, select_from = queryset._build_tables_select_from_relationship()
        expression = sqlalchemy.sql.select(*tables)
        expression = expression.select_from(select_from)

        if queryset._only:
            expression = expression.with_only_columns(*queryset._only)

        if queryset._defer:
            columns = [
                column for column in select_from.columns if column.name not in queryset._defer
            ]
            expression = expression.with_only_columns(*columns)

        if queryset._exclude_secrets:
            model_columns = queryset._secret_recursive_names(model_class=queryset.model_class)
            columns = [column for column in select_from.columns if column.name in model_columns]
            expression = expression.with_only_columns(*columns)

        expression = expression.where(await queryset.build_where_clause())

        if queryset._order_by:
            expression = queryset._build_order_by_expression(
                queryset._order_by, expression=expression
            )

        if queryset.limit_count:
            expression = expression.limit(queryset.limit_count)

        if queryset._offset:
            expression = expression.offset(queryset._offset)

        if queryset._group_by:
            expression = queryset._build_group_by_expression(
                queryset._group_by, expression=expression
            )

        if queryset.distinct_on is not None:
            expression = queryset._build_select_distinct(
                queryset.distinct_on, expression=expression
            )

        return expression

    def _filter_query(
        self,
        kwargs: Any,
        exclude: bool = False,
        or_: bool = False,
    ) -> "QuerySet":
        clauses = []
        filter_clauses = self.filter_clauses
        or_clauses = self.or_clauses
        select_related = list(self._select_related)
        prefetch_related = list(self._prefetch_related)

        # Making sure for queries we use the main class and not the proxy
        # And enable the parent
        if self.model_class.__is_proxy_model__:
            self.model_class = self.model_class.__parent__

        kwargs = clean_query_kwargs(
            self.model_class, kwargs, self.embed_parent_filters, model_database=self.database
        )

        for key, value in kwargs.items():
            model_class, field_name, op, related_str, _, cross_db_remainder = crawl_relationship(
                self.model_class, key
            )
            if related_str and related_str not in select_related:
                select_related.append(related_str)
            field = model_class.meta.fields.get(field_name, generic_field)
            if cross_db_remainder:
                assert field is not generic_field
                fk_field = cast(BaseForeignKey, field)
                sub_query = (
                    fk_field.target.query.filter(**{cross_db_remainder: value})
                    .only(*fk_field.related_columns.keys())
                    .values_list(fields=fk_field.related_columns.keys())
                )

                # bind local vars
                async def wrapper(
                    queryset: "QuerySet",
                    _field: "BaseFieldType" = field,
                    _sub_query: "QuerySet" = sub_query,
                ) -> Any:
                    fk_tuple = sqlalchemy.tuple_(
                        *(
                            getattr(queryset.table.columns, colname)
                            for colname in _field.get_column_names()
                        )
                    )
                    return fk_tuple.in_(await _sub_query)

                clauses.append(wrapper)
            elif callable(value):
                # bind local vars
                async def wrapper(
                    queryset: "QuerySet",
                    _field: "BaseFieldType" = field,
                    _value: Any = value,
                    _op: Optional[str] = op,
                ) -> Any:
                    _value = _value(queryset)
                    if isawaitable(_value):
                        _value = await _value
                    return _field.operator_to_clause(
                        _field.name,
                        _op,
                        queryset.model_class.table_schema(queryset.active_schema),
                        _value,
                    )

                clauses.append(wrapper)

            else:
                assert not isinstance(
                    value, BaseModelType
                ), f"should be parsed in clean: {key}: {value}"
                clauses.append(
                    field.operator_to_clause(
                        field_name, op, model_class.table_schema(self.active_schema), value
                    )
                )
        if exclude:

            async def wrapper(queryset: "QuerySet") -> Any:
                return clauses_mod.not_(
                    clauses_mod.and_(*(await self._resolve_clause_args(clauses)))
                )

            if not or_:
                filter_clauses.append(wrapper)
            else:
                or_clauses.append(wrapper)
        else:
            if not or_:
                filter_clauses += clauses
            else:
                or_clauses += clauses

        return cast(
            "QuerySet",
            self.__class__(
                model_class=self.model_class,
                database=self._database,
                filter_clauses=filter_clauses,
                or_clauses=or_clauses,
                select_related=select_related,
                prefetch_related=prefetch_related,
                limit_count=self.limit_count,
                limit_offset=self._offset,
                batch_size=self._batch_size,
                order_by=self._order_by,
                only_fields=self._only,
                defer_fields=self._defer,
                embed_parent=self.embed_parent,
                embed_parent_filters=self.embed_parent_filters,
                table=getattr(self, "_table", None),
                exclude_secrets=self._exclude_secrets,
                using_schema=self.using_schema,
            ),
        )

    def _prepare_order_by(self, order_by: str) -> Any:
        reverse = order_by.startswith("-")
        order_by = order_by.lstrip("-")
        order_col = self.table.columns[order_by]
        return order_col.desc() if reverse else order_col

    def _prepare_group_by(self, group_by: str) -> Any:
        group_by = group_by.lstrip("-")
        group_col = self.table.columns[group_by]
        return group_col

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
        self, row: Any, extra_attr: str = "", raw: bool = False
    ) -> tuple[EdgyModel, EdgyModel]:
        is_only_fields = bool(self._only)
        is_defer_fields = bool(self._defer)
        raw_result, result = (
            await self._cache.aget_or_cache_many(
                self.model_class,
                [row],
                cache_fn=lambda row: self.model_class.from_sqla_row(
                    row,
                    select_related=self._select_related,
                    is_only_fields=is_only_fields,
                    only_fields=self._only,
                    is_defer_fields=is_defer_fields,
                    prefetch_related=self._prefetch_related,
                    exclude_secrets=self._exclude_secrets,
                    using_schema=self.active_schema,
                    database=self.database,
                    table=self.table,
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
        return schema  # type: ignore

    def _clone(self) -> "QuerySet":
        """
        Return a copy of the current QuerySet that's ready for another
        operation.
        """
        queryset = self.__class__.__new__(self.__class__)
        queryset.model_class = self.model_class
        queryset._cache = QueryModelResultCache(attrs=queryset.model_class.pkcolumns)
        queryset._clear_cache()
        queryset.using_schema = self.using_schema

        # initialize
        queryset.active_schema = self.get_schema()

        queryset._table = getattr(self, "_table", None)
        queryset.filter_clauses = copy.copy(self.filter_clauses)
        queryset.or_clauses = copy.copy(self.or_clauses)
        queryset.limit_count = copy.copy(self.limit_count)
        queryset._select_related = copy.copy(self._select_related)
        queryset._prefetch_related = copy.copy(self._prefetch_related)
        queryset._offset = copy.copy(self._offset)
        queryset._order_by = copy.copy(self._order_by)
        queryset._group_by = copy.copy(self._group_by)
        queryset.distinct_on = copy.copy(self.distinct_on)
        queryset.embed_parent = self.embed_parent
        queryset.embed_parent_filters = self.embed_parent_filters
        queryset._batch_size = self._batch_size
        queryset._only = copy.copy(self._only)
        queryset._defer = copy.copy(self._defer)
        queryset._database = self.database
        queryset._exclude_secrets = self._exclude_secrets
        return cast("QuerySet", queryset)

    def _clear_cache(self, keep_result_cache: bool = False) -> None:
        if not keep_result_cache:
            self._cache.clear()
        self._cache_count: Optional[int] = None
        self._cache_first: Optional[tuple[BaseModelType, BaseModelType]] = None
        self._cache_last: Optional[tuple[BaseModelType, BaseModelType]] = None
        # fetch all is in cache
        self._cache_fetch_all: bool = False
        # get current row during iteration. Used for prefetching.
        # Bad style but no other way currently possible
        self._cache_current_row: Optional[sqlalchemy.Row] = None

    async def _handle_batch(
        self, batch: Sequence[sqlalchemy.Row], queryset: "BaseQuerySet"
    ) -> Sequence[tuple[BaseModelType, BaseModelType]]:
        is_only_fields = bool(queryset._only)
        is_defer_fields = bool(queryset._defer)
        del queryset
        _prefetch_related: list[Prefetch] = []

        clauses = []
        for pkcol in self.model_class.pkcolumns:
            clauses.append(
                getattr(self.table.columns, pkcol).in_([getattr(row, pkcol) for row in batch])
            )
        for prefetch in self._prefetch_related:
            check_prefetch_collision(self.model_class, prefetch)  # type: ignore

            crawl_result = crawl_relationship(
                self.model_class, prefetch.related_name, traverse_last=True
            )
            if crawl_result.cross_db_remainder:
                raise NotImplementedError(
                    "Cannot prefetch from other db yet. Maybe in future this feature will be added."
                )
            prefetch_queryset: Optional[QuerySet] = prefetch.queryset
            if prefetch_queryset is None:
                if crawl_result.reverse_path is False:
                    prefetch_queryset = self.model_class.query.filter(*clauses)
                else:
                    prefetch_queryset = crawl_result.model_class.query.filter(*clauses)
            else:
                prefetch_queryset = prefetch_queryset.filter(*clauses)

            if prefetch_queryset.model_class == self.model_class:
                # queryset is of this model
                prefetch_queryset = prefetch_queryset.select_related(prefetch.related_name)
                prefetch_queryset.embed_parent = (prefetch.related_name, "")
            elif crawl_result.reverse_path is False:
                QuerySetError(
                    detail=(
                        f"Creating a reverse path is not possible, unidirectional fields used."
                        f"You may want to use as queryset a queryset of model class {self.model_class!r}."
                    )
                )
            else:
                # queryset is of the target model
                prefetch_queryset = prefetch_queryset.select_related(crawl_result.reverse_path)
            new_prefetch = Prefetch(
                related_name=prefetch.related_name,
                to_attr=prefetch.to_attr,
                queryset=prefetch_queryset,
            )
            new_prefetch._is_finished = True
            _prefetch_related.append(new_prefetch)

        return cast(
            Sequence[tuple[BaseModelType, BaseModelType]],
            await self._cache.aget_or_cache_many(
                self.model_class,
                batch,
                cache_fn=lambda row: self.model_class.from_sqla_row(
                    row,
                    select_related=self._select_related,
                    is_only_fields=is_only_fields,
                    only_fields=self._only,
                    is_defer_fields=is_defer_fields,
                    prefetch_related=_prefetch_related,
                    exclude_secrets=self._exclude_secrets,
                    using_schema=self.active_schema,
                    database=self.database,
                    table=self.table,
                ),
                transform_fn=self._embed_parent_in_result,
            ),
        )

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

        expression = await queryset._build_select()

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
        check_db_connection(queryset.database)
        if fetch_all_at_once:
            async with queryset.database as database:
                batch = cast(Sequence[sqlalchemy.Row], await database.fetch_all(expression))
            for row_num, result in enumerate(await self._handle_batch(batch, queryset)):
                if counter == 0:
                    self._cache_first = result
                last_element = result
                counter += 1
                self._cache_current_row = batch[row_num]
                yield result[1]
            self._cache_current_row = None
            self._cache_fetch_all = True
        else:
            async with queryset.database as database:
                async for batch in database.batched_iterate(
                    expression, batch_size=self._batch_size
                ):
                    # clear only result cache
                    self._cache.clear()
                    self._cache_fetch_all = False
                    for row_num, result in enumerate(await self._handle_batch(batch, queryset)):
                        if counter == 0:
                            self._cache_first = result
                        last_element = result
                        counter += 1
                        self._cache_current_row = batch[row_num]  # type: ignore
                        yield result[1]
                self._cache_current_row = None
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
                "sqlalchemy.sql.expression.BinaryExpression",
                Callable[
                    ["QueryType"],
                    Union[
                        "sqlalchemy.sql.expression.BinaryExpression",
                        Awaitable["sqlalchemy.sql.expression.BinaryExpression"],
                    ],
                ],
            ]
        ],
        exclude: bool = False,
        or_: bool = False,
    ) -> "QuerySet":
        """
        Filters or excludes a given clause for a specific QuerySet.
        """
        queryset: QuerySet = self._clone()
        if kwargs:
            queryset = queryset._filter_query(kwargs, exclude=exclude, or_=or_)
        if not clauses:
            return queryset
        op = clauses_mod.or_ if or_ else clauses_mod.and_
        if exclude:
            queryset.filter_clauses.append(clauses_mod.not_(op(*clauses)))
        else:
            queryset.filter_clauses.append(op(*clauses))
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

        queryset: BaseQuerySet = self

        expression = (await queryset._build_select()).limit(2)
        check_db_connection(queryset.database)
        async with queryset.database as database:
            rows = await database.fetch_all(expression)

        if not rows:
            queryset._cache_count = 0
            raise ObjectNotFound()
        if len(rows) > 1:
            raise MultipleObjectsReturned()
        queryset._cache_count = 1

        return await queryset._get_or_cache_row(rows[0], "_cache_first,_cache_last")


class QuerySet(BaseQuerySet):
    """
    QuerySet object used for query retrieving. Public interface
    """

    @property
    def raw_query(self) -> Any:
        """Get SQL select query (sqlalchemy)."""
        return run_sync(self._build_select())

    @cached_property
    def sql(self) -> str:
        """Get SQL select query as string."""
        return str(self.raw_query)

    def filter(
        self,
        *clauses: Union[
            "sqlalchemy.sql.expression.BinaryExpression",
            Callable[
                ["QueryType"],
                Union[
                    "sqlalchemy.sql.expression.BinaryExpression",
                    Awaitable["sqlalchemy.sql.expression.BinaryExpression"],
                ],
            ],
        ],
        **kwargs: Any,
    ) -> "QuerySet":
        """
        Filters the QuerySet by the given kwargs and clauses.
        """
        return self._filter_or_exclude(clauses=clauses, kwargs=kwargs)

    def all(self, clear_cache: bool = False) -> "QuerySet":
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
            "sqlalchemy.sql.expression.BinaryExpression",
            Callable[
                ["QueryType"],
                Union[
                    "sqlalchemy.sql.expression.BinaryExpression",
                    Awaitable["sqlalchemy.sql.expression.BinaryExpression"],
                ],
            ],
        ],
        **kwargs: Any,
    ) -> "QuerySet":
        """
        Filters the QuerySet by the OR operand.
        """
        return self._filter_or_exclude(clauses=clauses, or_=True, kwargs=kwargs)

    def and_(
        self,
        *clauses: Union[
            "sqlalchemy.sql.expression.BinaryExpression",
            Callable[
                ["QueryType"],
                Union[
                    "sqlalchemy.sql.expression.BinaryExpression",
                    Awaitable["sqlalchemy.sql.expression.BinaryExpression"],
                ],
            ],
        ],
        **kwargs: Any,
    ) -> "QuerySet":
        """
        Filters the QuerySet by the AND operand. Alias of filter.
        """
        return self.filter(*clauses, **kwargs)

    def not_(
        self,
        *clauses: Union[
            "sqlalchemy.sql.expression.BinaryExpression",
            Callable[
                ["QueryType"],
                Union[
                    "sqlalchemy.sql.expression.BinaryExpression",
                    Awaitable["sqlalchemy.sql.expression.BinaryExpression"],
                ],
            ],
        ],
        **kwargs: Any,
    ) -> "QuerySet":
        """
        Filters the QuerySet by the NOT operand. Alias of exclude.
        """
        return self.exclude(*clauses, **kwargs)

    def exclude(
        self,
        *clauses: Union[
            "sqlalchemy.sql.expression.BinaryExpression",
            Callable[
                ["QueryType"],
                Union[
                    "sqlalchemy.sql.expression.BinaryExpression",
                    Awaitable["sqlalchemy.sql.expression.BinaryExpression"],
                ],
            ],
        ],
        **kwargs: Any,
    ) -> "QuerySet":
        """
        Exactly the same as the filter but for the exclude.
        """
        return self._filter_or_exclude(clauses=clauses, exclude=True, kwargs=kwargs)

    def exclude_secrets(
        self,
        exclude_secrets: bool = True,
    ) -> "QuerySet":
        """
        Excludes any field that contains the `secret=True` declared from being leaked.
        """
        queryset = self._clone()
        queryset._exclude_secrets = exclude_secrets
        return queryset

    def batch_size(
        self,
        batch_size: Optional[int] = None,
    ) -> "QuerySet":
        """
        Set batch/chunk size. Used for iterate
        """
        queryset = self._clone()
        queryset._batch_size = batch_size
        return queryset

    def lookup(self, term: Any) -> "QuerySet":
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

    def order_by(self, *order_by: str) -> "QuerySet":
        """
        Returns a QuerySet ordered by the given fields.
        """
        queryset: QuerySet = self._clone()
        queryset._order_by = order_by
        return queryset

    def reverse(self) -> "QuerySet":
        queryset: QuerySet = self._clone()
        queryset._order_by = [
            el[1:] if el.startswith("-") else f"-{el}" for el in queryset._order_by
        ]
        return queryset

    def limit(self, limit_count: int) -> "QuerySet":
        """
        Returns a QuerySet limited by.
        """
        queryset: QuerySet = self._clone()
        queryset.limit_count = limit_count
        return queryset

    def offset(self, offset: int) -> "QuerySet":
        """
        Returns a Queryset limited by the offset.
        """
        queryset: QuerySet = self._clone()
        queryset._offset = offset
        return queryset

    def group_by(self, *group_by: Sequence[str]) -> "QuerySet":
        """
        Returns the values grouped by the given fields.
        """
        queryset: QuerySet = self._clone()
        queryset._group_by = group_by
        return queryset

    def distinct(self, *distinct_on: str) -> "QuerySet":
        """
        Returns a queryset with distinct results.
        """
        queryset: QuerySet = self._clone()
        queryset.distinct_on = distinct_on
        return queryset

    def only(self, *fields: str) -> "QuerySet":
        """
        Returns a list of models with the selected only fields and always the primary
        key.
        """
        only_fields = [sqlalchemy.text(field) for field in fields]
        missing = []
        if self.model_class.pknames:
            for pkname in self.model_class.pknames:
                if pkname not in fields:
                    for pkcolumn in self.model_class.meta.get_columns_for_name(pkname):
                        missing.append(sqlalchemy.text(pkcolumn.key))
        else:
            for pkcolumn in self.model_class.pkcolumns:
                missing.append(sqlalchemy.text(pkcolumn.key))
        if missing:
            only_fields = missing + only_fields

        queryset: QuerySet = self._clone()
        queryset._only = only_fields
        return queryset

    def defer(self, *fields: Sequence[str]) -> "QuerySet":
        """
        Returns a list of models with the selected only fields and always the primary
        key.
        """
        queryset: QuerySet = self._clone()
        queryset._defer = fields
        return queryset

    def select_related(self, related: Any) -> "QuerySet":
        """
        Returns a QuerySet that will “follow” foreign-key relationships, selecting additional
        related-object data when it executes its query.

        This is a performance booster which results in a single more complex query but means

        later use of foreign-key relationships won’t require database queries.
        """
        queryset: QuerySet = self._clone()
        if not isinstance(related, (list, tuple)):
            related = [related]

        related = list(queryset._select_related) + related
        queryset._select_related = related
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

        if fields is not None and not isinstance(fields, CollectionsIterable):
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
        expression = await queryset._build_select()
        expression = sqlalchemy.exists(expression).select()
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
        expression = (await queryset._build_select()).alias("subquery_for_count")
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
        check_db_connection(queryset.database)
        async with queryset.database as database:
            row = await database.fetch_one(await queryset._build_select(), pos=0)
        if row:
            return (await self._get_or_cache_row(row, extra_attr="_cache_first"))[1]
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
        check_db_connection(queryset.database)
        async with queryset.database as database:
            row = await database.fetch_one(await queryset.reverse()._build_select(), pos=0)
        if row:
            return (await self._get_or_cache_row(row, extra_attr="_cache_last"))[1]
        return None

    async def create(self, *args: Any, **kwargs: Any) -> EdgyEmbedTarget:
        """
        Creates a record in a specific table.
        """
        # for tenancy
        queryset: QuerySet = self._clone()
        instance = self.model_class(*args, **kwargs)
        apply_instance_extras(
            instance,
            self.model_class,
            schema=self.using_schema,
            table=queryset.table,
            database=queryset.database,
        )
        # values=kwargs is required for ensuring all kwargs are seen as explicit kwargs
        instance = await instance.save(force_insert=True, values=set(kwargs.keys()))
        result = await self._embed_parent_in_result(instance)
        self._clear_cache(True)
        self._cache.update([result])
        return cast(EdgyEmbedTarget, result[1])

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

    async def delete(self, use_models: bool = False) -> int:
        if (
            self.model_class.__require_model_based_deletion__
            or self.model_class.meta.post_delete_fields
        ):
            use_models = True
        if use_models:
            return await self._model_based_delete()

        # delete of model issues already signals, so don't integrate them
        await self.model_class.meta.signals.pre_delete.send_async(self.__class__, instance=self)

        expression = self.table.delete()
        expression = expression.where(await self.build_where_clause())

        check_db_connection(self.database)
        async with self.database as database:
            row_count = cast(int, await database.execute(expression))

        # clear cache before executing post_delete. Fresh results can be retrieved in signals
        self._clear_cache()

        await self.model_class.meta.signals.post_delete.send_async(self.__class__, instance=self)
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
        await self.model_class.meta.signals.pre_update.send_async(
            self.__class__, instance=self, kwargs=column_values
        )

        expression = self.table.update().values(**column_values)
        expression = expression.where(await self.build_where_clause())
        check_db_connection(self.database)
        async with self.database as database:
            await database.execute(expression)

        # Broadcast the update executed
        await self.model_class.meta.signals.post_update.send_async(self.__class__, instance=self)
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

    def transaction(self, *, force_rollback: bool = False, **kwargs: Any) -> "Transaction":
        """Return database transaction for the assigned database."""
        return self.database.transaction(force_rollback=force_rollback, **kwargs)

    def __await__(
        self,
    ) -> Generator[Any, None, list[Any]]:
        return self._execute_all().__await__()

    async def __aiter__(self) -> AsyncIterator[Any]:
        async for value in self._execute_iterate():
            yield value
