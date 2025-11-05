from __future__ import annotations

import warnings
from collections.abc import (
    AsyncGenerator,
    AsyncIterator,
    Awaitable,
    Callable,
    Iterable,
    Sequence,
)
from contextvars import ContextVar
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

from edgy.core.db.context_vars import CURRENT_INSTANCE, MODEL_GETATTR_BEHAVIOR, get_schema
from edgy.core.db.datastructures import QueryModelResultCache
from edgy.core.db.fields.base import BaseForeignKey, RelationshipField
from edgy.core.db.models.types import BaseModelType
from edgy.core.db.relationships.utils import crawl_relationship
from edgy.core.utils.db import check_db_connection, hash_tablekey
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
    from edgy.core.connection import Database
    from edgy.core.db.fields.types import BaseFieldType
    from edgy.core.db.querysets.queryset import QuerySet


_empty_set = cast(Sequence[Any], frozenset())
# get current row during iteration. Used for prefetching.
_current_row_holder: ContextVar[list[sqlalchemy.Row | None] | None] = ContextVar(
    "_current_row_holder", default=None
)


def get_table_key_or_name(table: sqlalchemy.Table | sqlalchemy.Alias) -> str:
    """
    Retrieves the key or name of a SQLAlchemy table or alias.

    Args:
        table (sqlalchemy.Table | sqlalchemy.Alias): The SQLAlchemy table or alias object.

    Returns:
        str: The key or name of the table/alias.
    """
    try:
        return table.key  # type: ignore
    except AttributeError:
        # alias
        return table.name


def _extract_unique_lookup_key(obj: Any, unique_fields: Sequence[str]) -> tuple | None:
    """
    Extracts a unique lookup key from an object or dictionary based on a sequence of fields.

    Args:
        obj (Any): The object or dictionary from which to extract the lookup key.
        unique_fields (Sequence[str]): A sequence of field names that constitute the unique key.

    Returns:
        tuple | None: A tuple representing the unique lookup key, or None if any unique field
                      is missing in the object/dictionary.
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
    """Internal definitions for queryset."""

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
        # Have the user passed select related values copied
        select_related = set(select_related)
        # Have the **real** path values
        self._select_related: set[str] = set()
        # computed only, replacable. Have the **real** path values
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
        # private attribute which manipulates the prefix of filters, order_by, select_related
        # set by relations
        self.embed_parent_filters: tuple[str, str | str] | None = None
        self.using_schema = using_schema
        self._extra_select = list(extra_select) if extra_select is not None else []
        self._reference_select = (
            reference_select.copy() if isinstance(reference_select, dict) else {}
        )
        self._exclude_secrets = exclude_secrets
        # cache should not be cloned
        self._cache = QueryModelResultCache(attrs=self.model_class.pkcolumns)
        # is empty
        self._clear_cache(keep_result_cache=False)
        # this is not cleared, because the expression is immutable
        self._cached_select_related_expression: (
            tuple[Any, dict[str, tuple[sqlalchemy.Table, type[BaseModelType]]]] | None
        ) = None
        # initialize
        self.active_schema = self.get_schema()
        self._for_update: dict[str, Any] | None = None

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
        # copy but don't trigger update select related
        queryset._select_related.update(self._select_related)
        queryset._select_related_weak.update(self._select_related_weak)
        queryset._cached_select_related_expression = self._cached_select_related_expression
        queryset._for_update = self._for_update.copy() if self._for_update is not None else None
        return cast("QuerySet", queryset)

    @cached_property
    def _has_dynamic_clauses(self) -> bool:
        """
        Indicates if the queryset has any dynamic (callable) filter or OR clauses.
        """
        return any(callable(clause) for clause in chain(self.filter_clauses, self.or_clauses))

    def _clear_cache(
        self, *, keep_result_cache: bool = False, keep_cached_selected: bool = False
    ) -> None:
        """
        Clears the internal cache of the queryset.

        Args:
            keep_result_cache (bool): If True, the result cache (for fetched models) is preserved.
                                      Defaults to False.
            keep_cached_selected (bool): If True, the cached select expression and tables are preserved.
                                         Defaults to False.
        """
        if not keep_result_cache:
            self._cache.clear()
        if not keep_cached_selected:
            self._cached_select_with_tables: (
                tuple[Any, dict[str, tuple[sqlalchemy.Table, type[BaseModelType]]]] | None
            ) = None
        self._cache_count: int | None = None
        self._cache_first: tuple[BaseModelType, Any] | None = None
        self._cache_last: tuple[BaseModelType, Any] | None = None
        # fetch all is in cache
        self._cache_fetch_all: bool = False

    def _build_order_by_iterable(
        self, order_by: Iterable[str], tables_and_models: tables_and_models_type
    ) -> Iterable:
        """Builds the iterator for a order by like expression."""
        return (self._prepare_order_by(entry, tables_and_models) for entry in order_by)

    async def build_where_clause(
        self, _: Any = None, tables_and_models: tables_and_models_type | None = None
    ) -> Any:
        """
        Builds a SQLAlchemy WHERE clause from the queryset's filter and OR clauses.

        Args:
            _ (Any): Ignored. Used for compatibility with `clauses_mod.parse_clause_arg` signature.
            tables_and_models (tables_and_models_type | None): A dictionary mapping table aliases to
                                                               (table, model) tuples. If None, it's
                                                               built internally. Defaults to None.

        Returns:
            Any: The combined SQLAlchemy WHERE clause.
        """
        joins: Any | None = None
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

    def _build_select_distinct(
        self,
        distinct_on: Sequence[str] | None,
        expression: Any,
        tables_and_models: tables_and_models_type,
    ) -> Any:
        """Filters selects only specific fields. Leave empty to use simple distinct"""
        # using with columns is not supported by all databases
        if distinct_on:
            return expression.distinct(
                *(
                    self._prepare_distinct(distinct_el, tables_and_models)
                    for distinct_el in distinct_on
                )
            )
        else:
            return expression.distinct()

    @classmethod
    def _join_table_helper(
        cls,
        join_clause: Any,
        current_transition: tuple[str, str, str],
        *,
        transitions: dict[tuple[str, str, str], tuple[Any, tuple[str, str, str] | None, str]],
        tables_and_models: dict[str, tuple[sqlalchemy.Table, type[BaseModelType]]],
    ) -> Any:
        """
        Recursively builds SQLAlchemy join clauses based on a transition map.

        Args:
            join_clause (Any): The current join clause to which new joins are added.
            current_transition (tuple[str, str, str]): The key for the current transition.
            transitions (dict[tuple[str, str, str], tuple[Any, tuple[str, str, str] | None, str]]):
                A dictionary mapping transition keys to (join_condition, parent_transition_key, table_alias) tuples.
            tables_and_models (dict[str, tuple[sqlalchemy.Table, type[BaseModelType]]]):
                A dictionary mapping table aliases to (table, model) tuples.

        Returns:
            Any: The updated join clause.
        """
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
        Builds the table relationships and joins for `select_related` operations.

        This method constructs a graph of table joins based on the `_select_related` paths.
        It handles many-to-many relationships and aliasing of tables to ensure uniqueness.
        The result is cached for performance.

        Returns:
            tuple[Any, tables_and_models_type]: A tuple containing:
                - The SQLAlchemy join expression.
                - A dictionary mapping table aliases (prefixes) to (table, model) tuples.

        Raises:
            QuerySetError: If a selected field does not exist or is not a RelationshipField,
                           or if a selected model is on another database.
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
                tuple[str, str, str], tuple[Any, tuple[str, str, str] | None, str]
            ] = {}

            # Select related
            for select_path in self._select_related.union(self._select_related_weak):
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

                injected_prefix: bool | str = False
                model_database: Database | None = self.database
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
                        foreign_key: BaseForeignKey = field
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
                    if foreign_key.is_m2m and foreign_key.embed_through != "":
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
        """
        Generates SQLAlchemy WHERE clauses for joining tables based on a foreign key relationship.

        Args:
            foreign_key (BaseForeignKey): The foreign key field defining the relationship.
            table (Any): The SQLAlchemy table for the related model.
            reverse (bool): True if the relationship is being traversed in reverse (from related to source model).
            former_table (Any): The SQLAlchemy table for the source model.

        Yields:
            Any: SQLAlchemy binary expressions for the join condition.
        """
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
        """
        Validates that .only() and .defer() are not used simultaneously.

        Raises:
            QuerySetError: If both .only() and .defer() are applied to the queryset.
        """
        if self._only and self._defer:
            raise QuerySetError("You cannot use .only() and .defer() at the same time.")

    async def _as_select_with_tables(
        self,
    ) -> tuple[Any, tables_and_models_type]:
        """
        Builds the SQLAlchemy SELECT expression along with the mapping of tables and models,
        based on the queryset's parameters and filters.

        This method handles `only`, `defer`, `exclude_secrets`, `extra_select`, and
        `reference_select` clauses, and incorporates `select_related` joins.

        Returns:
            tuple[Any, tables_and_models_type]: A tuple containing:
                - The constructed SQLAlchemy SELECT expression.
                - A dictionary mapping table aliases to (table, model) tuples.

        Raises:
            AssertionError: If no columns or extra_select elements are specified for the query.
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
            expression = expression.order_by(
                *self._build_order_by_iterable(self._order_by, tables_and_models)
            )

        if self._group_by:
            expression = expression.group_by(
                *self._build_order_by_iterable(self._group_by, tables_and_models)
            )

        if self.limit_count:
            expression = expression.limit(self.limit_count)

        if self._offset:
            expression = expression.offset(self._offset)

        if self.distinct_on is not None:
            expression = self._build_select_distinct(
                self.distinct_on, expression=expression, tables_and_models=tables_and_models
            )

        if self._for_update:
            params = dict(self._for_update)
            # If user provided model classes via "of", map them to the actual tables
            # (including aliases) present in this SELECT. Postgres requires FROM members.
            if "of" in params and params["of"]:
                target_models = set(params["of"])
                of_tables: list[Any] = []
                for _, (table, model) in tables_and_models.items():
                    if model in target_models:
                        of_tables.append(table)
                if of_tables:
                    params["of"] = tuple(of_tables)
                else:
                    params.pop("of", None)
            expression = expression.with_for_update(**params)
        return expression, tables_and_models

    async def as_select_with_tables(
        self,
    ) -> tuple[Any, tables_and_models_type]:
        """
        Builds the query select based on the given parameters and filters, including
        the mapping of tables and models involved in the query. The result is cached.

        Returns:
            tuple[Any, tables_and_models_type]: A tuple containing the SQLAlchemy select
                                                 expression and the tables and models dictionary.
        """
        if self._cached_select_with_tables is None:
            self._cached_select_with_tables = await self._as_select_with_tables()
        return self._cached_select_with_tables

    async def as_select(
        self,
    ) -> Any:
        """
        Builds and returns only the SQLAlchemy select expression for the current queryset.

        Returns:
            Any: The SQLAlchemy select expression.
        """
        return (await self.as_select_with_tables())[0]

    def _kwargs_to_clauses(
        self,
        kwargs: Any,
    ) -> tuple[list[Any], set[str]]:
        """
        Converts keyword arguments into a list of callable filter clauses and a set of
        `select_related` paths.

        This function handles relationship traversal and cross-database foreign keys,
        generating appropriate SQLAlchemy expressions or wrapped async functions.

        Args:
            kwargs (Any): The keyword arguments representing the filter conditions.

        Returns:
            tuple[list[Any], set[str]]: A tuple containing:
                - A list of SQLAlchemy binary expressions or async callable wrappers.
                - A set of relationship paths for `select_related`.
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
                    _op: str | None = op,
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

    def _prepare_order_by(self, order_by: str, tables_and_models: tables_and_models_type) -> Any:
        """
        Prepares an order_by or group_by clause from a string.

        Args:
            order_by (str): The field name for ordering, optionally prefixed with '-' for descending.

        Returns:
            Any: The SQLAlchemy column expression for ordering and the select_path.
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
        """
        Update _select_related_weak

        Args:
            fields (Iterable[str]): The field names of order_by, group_by, ...

        """
        related: set[str] = set()
        for field_name in fields:
            # handle order by values by stripping -
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
        """
        Update _select_related

        Args:
            pathes (Iterable[str]): The related pathes.

        """
        related: set[str] = set()
        for path in pathes:
            # handle order by values by stripping -
            path = path.lstrip("-")
            crawl_result = clauses_mod.clean_path_to_crawl_result(
                self.model_class,
                # actually not a field_path
                path=path,
                embed_parent=self.embed_parent_filters,
                model_database=self.database,
            )
            # actually not a field name
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
        """
        Prepares a field for use in a distinct-on clause.

        Args:
            distinct_on (str): The field name for distinctness.

        Returns:
            sqlalchemy.Column: The SQLAlchemy column object.
        """
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
        Embeds a parent model into the result if `embed_parent` is configured.

        This allows accessing related models directly from the main model instance
        as defined by the `embed_parent` setting.

        Args:
            result (EdgyModel | Awaitable[EdgyModel]): The model instance or an awaitable
                                                        that resolves to a model instance.

        Returns:
            tuple[EdgyModel, Any]: A tuple where the first element is the original result
                                   and the second is the potentially embedded result.
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

    async def _get_or_cache_row(
        self,
        row: Any,
        tables_and_models: dict[str, tuple[sqlalchemy.Table, type[BaseModelType]]],
        extra_attr: str = "",
        raw: bool = False,
    ) -> tuple[EdgyModel, EdgyEmbedTarget]:
        """
        Retrieves or caches a single model instance from a SQLAlchemy row.

        This method converts a SQLAlchemy row into a model instance, handles
        `only_fields`, `defer_fields`, `prefetch_related`, and `embed_parent` configurations,
        and optionally sets extra attributes on the queryset for caching.

        Args:
            row (Any): The SQLAlchemy row object.
            tables_and_models (dict[str, tuple[sqlalchemy.Table, type[BaseModelType]]]):
                A dictionary mapping table aliases to (table, model) tuples.
            extra_attr (str): Comma-separated string of attributes to set on the queryset with the result.
                              Defaults to "".
            raw (bool): If True, returns the raw model instance without `embed_parent` transformation.
                        Defaults to False.

        Returns:
            tuple[EdgyModel, EdgyEmbedTarget]: A tuple containing the raw model instance
                                               and the potentially embedded target instance.
        """
        is_defer_fields = bool(self._defer)
        result_tuple: tuple[EdgyModel, EdgyEmbedTarget] = (
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
                setattr(self, attr, result_tuple)
        return result_tuple

    def get_schema(self) -> str | None:
        """
        Retrieves the active database schema for the queryset.

        The schema can be explicitly set via `using_schema`, obtained from the
        current context variable, or derived from the model's metadata.

        Returns:
            str | None: The active schema name, or None if not applicable.
        """
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
        new_cache: QueryModelResultCache,
    ) -> Sequence[tuple[BaseModelType, BaseModelType]]:
        """
        Handles a batch of SQLAlchemy rows, converting them to model instances and
        performing prefetching operations.

        Args:
            batch (Sequence[sqlalchemy.Row]): A sequence of SQLAlchemy row objects.
            tables_and_models (dict[str, tuple[sqlalchemy.Table, type[BaseModelType]]]):
                A dictionary mapping table aliases to (table, model) tuples.
            queryset (BaseQuerySet): The current queryset (used for its configuration).
            new_cache (QueryModelResultCache): The cache to store the new batch results.

        Returns:
            Sequence[tuple[EdgyModel, EdgyEmbedTarget]]: A sequence of tuples, each containing
                                                            the raw model instance and the embedded target.

        Raises:
            NotImplementedError: If prefetching from another database is attempted.
            QuerySetError: If creating a reverse path for prefetching is not possible.
        """
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
                # ensure local or
                prefetch_queryset = prefetch_queryset.local_or(*clauses)

            if prefetch_queryset.model_class is self.model_class:
                # queryset is of this model
                prefetch_queryset = prefetch_queryset.select_related(prefetch.related_name)
                prefetch_queryset.embed_parent = (prefetch.related_name, "")
            else:
                # queryset is of the target model
                prefetch_queryset = prefetch_queryset.select_related(crawl_result.reverse_path)
            new_prefetch = Prefetch(
                related_name=prefetch.related_name,
                to_attr=prefetch.to_attr,
                queryset=prefetch_queryset,
            )
            new_prefetch._bake_prefix = f"{hash_tablekey(tablekey=tables_and_models[''][0].key, prefix=crawl_result.reverse_path)}_"
            new_prefetch._is_finished = True
            _prefetch_related.append(new_prefetch)

        return await new_cache.aget_or_cache_many(
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
            old_cache=self._cache,
        )

    @property
    def _current_row(self) -> sqlalchemy.Row | None:
        """Get async safe the current row when in _execute_iterate"""
        row_holder = _current_row_holder.get()
        if not row_holder:
            return None
        return row_holder[0]

    async def _execute_iterate(
        self, fetch_all_at_once: bool = False
    ) -> AsyncIterator[BaseModelType]:
        """
        Executes the query and yields model instances during iteration.

        This method supports fetching all results at once or in batches, and handles
        prefetching and embedding parent models. It also includes warnings for
        `force_rollback` usage with iterations due to potential deadlocks.

        Args:
            fetch_all_at_once (bool): If True, all results are fetched before yielding.
                                      Defaults to False.

        Yields:
            BaseModelType: A model instance for each row.

        Warns:
            UserWarning: If using queryset iterations with `Database`-level `force_rollback` enabled.
        """
        if self._cache_fetch_all:
            for result in cast(
                Sequence[tuple[BaseModelType, BaseModelType]],
                self._cache.get_category(self.model_class).values(),
            ):
                yield result[1]
            return
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
        last_element: tuple[BaseModelType, BaseModelType] | None = None
        check_db_connection(queryset.database, stacklevel=4)
        current_row: list[sqlalchemy.Row | None] = [None]
        token = _current_row_holder.set(current_row)
        try:
            if fetch_all_at_once:
                # we need a new cache to have the right order
                new_cache = QueryModelResultCache(self._cache.attrs)
                async with queryset.database as database:
                    batch = cast(Sequence[sqlalchemy.Row], await database.fetch_all(expression))
                for row_num, result in enumerate(
                    await self._handle_batch(
                        batch, tables_and_models, queryset, new_cache=new_cache
                    )
                ):
                    if counter == 0:
                        self._cache_first = result
                    last_element = result
                    counter += 1
                    current_row[0] = batch[row_num]
                    yield result[1]
                self._cache_fetch_all = True
                self._cache = new_cache
            else:
                batch_num: int = 0
                new_cache = QueryModelResultCache(self._cache.attrs)
                async with queryset.database as database:
                    async for batch in cast(
                        AsyncGenerator[Sequence[sqlalchemy.Row], None],
                        database.batched_iterate(expression, batch_size=self._batch_size),
                    ):
                        # clear only result cache
                        new_cache.clear()
                        self._cache_fetch_all = False
                        for row_num, result in enumerate(
                            await self._handle_batch(batch, tables_and_models, queryset, new_cache)
                        ):
                            if counter == 0:
                                self._cache_first = result
                            last_element = result
                            counter += 1
                            current_row[0] = batch[row_num]
                            yield result[1]
                        batch_num += 1
                if batch_num <= 1:
                    self._cache = new_cache
                    self._cache_fetch_all = True

        finally:
            _current_row_holder.reset(token)
        # better update them once
        self._cache_count = counter
        self._cache_last = last_element

    async def _execute_all(self) -> list[EdgyModel]:
        """
        Executes the query and returns all results as a list of model instances.
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
        Filters or excludes a given clause for a specific QuerySet.

        This is an internal method used by `filter`, `exclude`, `or_`, and `and_` to
        construct the query's WHERE clauses. It handles various clause types including
        dictionaries (kwargs), callable filters, and other QuerySet objects.

        Args:
            kwargs (Any): Additional keyword arguments to filter by.
            clauses (Sequence[...]): A sequence of filter clauses.
            exclude (bool): If True, the clauses are inverted for exclusion. Defaults to False.
            or_ (bool): If True, the clauses are combined with OR. Defaults to False.
            allow_global_or (bool): If True, and only one OR clause is provided, it can be
                                    added to the queryset's global OR clauses. Defaults to True.

        Returns:
            QuerySet: A new QuerySet with the applied filters/exclusions.

        Raises:
            AssertionError: If `exclude` is True and `or_` is also True when adding to global OR.
            AssertionError: If a `QuerySet` object is used as a clause with a different model class.
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

    async def _model_based_delete(self, remove_referenced_call: str | bool) -> int:
        """
        Performs a model-based deletion, iterating through models and calling their `raw_delete` method.

        This method is used when `__require_model_based_deletion__` or `post_delete_fields` are set
        on the model, ensuring hooks and related object handling are executed.

        Args:
            remove_referenced_call (str | bool): Specifies how to handle referenced objects during deletion.

        Returns:
            int: The total number of records deleted.
        """
        queryset = self.limit(self._batch_size) if not self._cache_fetch_all else self
        # we set embed_parent on the copy to None to get raw instances
        # embed_parent_filters is not affected
        queryset.embed_parent = None
        row_count = 0
        models = await queryset
        token = CURRENT_INSTANCE.set(cast("QuerySet", self))
        try:
            while models:
                for model in models:
                    await model.raw_delete(
                        skip_post_delete_hooks=False, remove_referenced_call=remove_referenced_call
                    )
                    row_count += 1
                # clear cache and fetch new batch
                models = await queryset.all(True)
        finally:
            CURRENT_INSTANCE.reset(token)
        return row_count

    async def raw_delete(
        self, use_models: bool = False, remove_referenced_call: str | bool = False
    ) -> int:
        """
        Executes a raw delete operation on the database.

        This method can either perform a direct SQL DELETE statement or iterate
        through models and call their individual `raw_delete` methods based on
        `use_models` and model configurations.

        Args:
            use_models (bool): If True, deletion is performed by iterating and
                               deleting individual model instances. Defaults to False.
            remove_referenced_call (str | bool): Specifies how to handle referenced objects during deletion.

        Returns:
            int: The number of rows deleted.
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
            expression = self.table.delete()
            expression = expression.where(await self.build_where_clause())

            check_db_connection(self.database)
            async with self.database as database:
                row_count = cast(int, await database.execute(expression))

        # clear cache before executing post_delete. Fresh results can be retrieved in signals
        self._clear_cache()

        return row_count

    async def _get_raw(self, **kwargs: Any) -> tuple[BaseModelType, Any]:
        """
        Returns a single record based on the given kwargs.

        This is an internal method that fetches a single row from the database,
        handling caching and raising exceptions for no results or multiple results.

        Args:
            **kwargs (Any): Keyword arguments to filter the query.

        Returns:
            tuple[BaseModelType, Any]: A tuple containing the raw model instance and
                                       the potentially embedded target instance.

        Raises:
            ObjectNotFound: If no object matches the given criteria.
            MultipleObjectsReturned: If more than one object matches the criteria.
        """

        if kwargs:
            cached = cast(
                tuple[BaseModelType, Any] | None, self._cache.get(self.model_class, kwargs)
            )
            if cached is not None:
                return cached
            filter_query = cast("BaseQuerySet", self.filter(**kwargs))
            # connect parent query cache
            filter_query._cache = self._cache
            return await filter_query._get_raw()
        elif self._cache_count == 1:
            if self._cache_first is not None:
                return self._cache_first
            elif self._cache_last is not None:
                return self._cache_last

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
