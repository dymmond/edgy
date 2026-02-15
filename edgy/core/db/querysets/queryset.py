from __future__ import annotations

import warnings
from collections.abc import (
    AsyncIterator,
    Awaitable,
    Callable,
    Generator,
    Iterable,
    Sequence,
)
from functools import cached_property
from typing import (
    TYPE_CHECKING,
    Any,
    Literal,
    cast,
)

import sqlalchemy

from edgy.core.db.context_vars import CURRENT_INSTANCE
from edgy.core.db.fields import CharField, TextField
from edgy.core.db.models.model_reference import ModelRef
from edgy.core.db.models.types import BaseModelType
from edgy.core.db.models.utils import apply_instance_extras
from edgy.core.db.querysets.base import BaseQuerySet, _extract_unique_lookup_key
from edgy.core.db.querysets.parser import ResultParser
from edgy.core.utils.concurrency import run_concurrently
from edgy.core.utils.db import CHECK_DB_CONNECTION_SILENCED, check_db_connection
from edgy.core.utils.sync import run_sync
from edgy.exceptions import ObjectNotFound, QuerySetError

from .types import (
    EdgyEmbedTarget,
    EdgyModel,
    QuerySetType,
    reference_select_type,
)

if TYPE_CHECKING:  # pragma: no cover
    from databasez.core.transaction import Transaction

    from edgy.core.db.querysets.mixins.combined import CombinedQuerySet


class QuerySet(BaseQuerySet):
    @cached_property
    def sql(self) -> str:
        """Get SQL select query as string with inserted blanks. For debugging only!"""
        return str(run_sync(self._sql_helper()))

    def _combine(
        self,
        other: QuerySet,
        op: Literal["union", "intersect", "except"],
        *,
        all_: bool = False,
    ) -> CombinedQuerySet:
        """
        Internal helper used by `union()`, `intersect()`, and `except_()` to build
        a CombinedQuerySet.

        We keep the core set operation in `op` and pass the `all_` flag through
        so that CombinedQuerySet (and its compiler) can decide whether to emit
        e.g. `UNION` vs `UNION ALL`.

        Args:
            other: The secondary `QuerySet` to combine results with.
            op: The base set operation type ('union', 'intersect', or 'except').
            all_: If `True`, requests the ALL variant of the set operation (e.g. UNION ALL).

        Returns:
            A `CombinedQuerySet` instance configured for the specified set operation.

        Raises:
            TypeError: If `other` is not an instance of `QuerySet`.
            QuerySetError: If the models (`self.model_class` and `other.model_class`)
                           of the two querysets do not match.
        """
        from edgy.core.db.querysets.mixins.combined import CombinedQuerySet

        # Check type of the other object
        if not isinstance(other, QuerySet):
            raise TypeError("other must be a QuerySet")

        # Check model class consistency
        if self.model_class is not other.model_class:
            raise QuerySetError(detail="Both querysets must have the same model_class to combine.")

        # Map (op, all_) to a concrete set-op name understood by CombinedQuerySet
        if all_:
            if op == "union":
                op_name: str = "union_all"
            elif op == "intersect":
                op_name = "intersect_all"
            elif op == "except":
                op_name = "except_all"
            else:
                op_name = op  # type: ignore
        else:
            op_name = op

        return CombinedQuerySet(left=self, right=other, op=op_name)

    def union(self, other: QuerySet, *, all: bool = False) -> CombinedQuerySet:
        """
        Returns a result set that is the UNION of the current QuerySet and another QuerySet.

        By default, `UNION` returns only distinct rows (UNION DISTINCT).
        If `all=True`, it returns `UNION ALL`, which includes duplicate rows.

        Args:
            other: The other `QuerySet` to combine results with.
            all: If `True`, performs `UNION ALL`; otherwise, performs `UNION DISTINCT`.

        Returns:
            A `CombinedQuerySet` instance representing the combined operation.
        """
        return self._combine(other, "union", all_=all)

    def union_all(self, other: QuerySet) -> CombinedQuerySet:
        """
        Returns a result set that is the UNION ALL of the current QuerySet and another QuerySet.

        This is a shortcut method equivalent to calling `union(other, all=True)`.

        Args:
            other: The other `QuerySet` to combine results with.

        Returns:
            A `CombinedQuerySet` instance representing the UNION ALL operation.
        """
        return self._combine(other, "union", all_=True)

    def intersect(self, other: QuerySet, *, all: bool = False) -> CombinedQuerySet:
        """
        Returns a result set that is the INTERSECT (intersection) of the current QuerySet
        and another QuerySet.

        By default, `INTERSECT` returns only distinct rows (INTERSECT DISTINCT).
        If `all=True`, the behavior depends on the backend but typically implies `INTERSECT ALL`.

        Args:
            other: The other `QuerySet` to combine results with.
            all: If `True`, attempts to perform `INTERSECT ALL`; otherwise, performs `INTERSECT DISTINCT`.

        Returns:
            A `CombinedQuerySet` instance representing the combined operation.
        """
        return self._combine(other, "intersect", all_=all)

    def except_(self, other: QuerySet, *, all: bool = False) -> CombinedQuerySet:
        """
        Returns a result set that is the EXCEPT (difference) of the current QuerySet
        and another QuerySet (rows in the first but not in the second).

        By default, `EXCEPT` returns only distinct rows (EXCEPT DISTINCT).
        If `all=True`, performs `EXCEPT ALL`.

        Args:
            other: The other `QuerySet` to combine results with.
            all: If `True`, performs `EXCEPT ALL`; otherwise, performs `EXCEPT DISTINCT`.

        Returns:
            A `CombinedQuerySet` instance representing the combined operation.
        """
        return self._combine(other, "except", all_=all)

    async def _sql_helper(self) -> Any:
        """
        Helper method to compile the SQL query represented by the current QuerySet into a string.

        This is primarily used for debugging, introspection, or logging the generated SQL.
        The method ensures that literal bind values (parameters) are included in the final string.

        Returns:
            A string containing the compiled SQL query.
        """
        # Use the database context manager to ensure the engine is ready
        async with self.database:
            # 1. Get the SQLAlchemy Selectable object
            selectable = await self.as_select()

            # 2. Compile the selectable object using the database engine
            compiled_sql: Any = selectable.compile(
                self.database.engine,
                compile_kwargs={"literal_binds": True},  # Include parameter values directly
            )
            # Return the compiled statement (which often implicitly converts to a string)
            return compiled_sql

    def select_for_update(
        self,
        *,
        nowait: bool = False,
        skip_locked: bool = False,
        read: bool = False,
        key_share: bool = False,
        of: Sequence[type[BaseModelType]] | None = None,
    ) -> QuerySet:
        """
        Request row-level locks on the rows selected by this queryset, using
        dialect-appropriate SELECT ... FOR UPDATE semantics via SQLAlchemy's
        `with_for_update()`.

        Args:
            nowait (bool): Fail immediately if a lock cannot be acquired.
            skip_locked (bool): Skip rows that are locked by other transactions (where supported).
            read (bool): Shared lock variant (PostgreSQL's FOR SHARE).
            key_share (bool):PostgreSQL's FOR KEY SHARE.
            of (Sequence[type[BaseModelType]] | None): Models whose tables should be explicitly locked
                (PostgreSQL's OF ...). The models must be part of the FROM/JOIN set for this query.

        Notes:
            - Most databases require running inside an explicit transaction:
                  async with database.transaction():
                      ...
            - On unsupported dialects (e.g. SQLite), this is a no-op.
            - For PostgreSQL, `read=True` maps to FOR SHARE and `key_share=True` to FOR KEY SHARE.
            - `of=[ModelA, ...]` restricts locking to specific tables (PostgreSQL only).
              You should include related models in the query via `select_related(...)`
              if you plan to lock them with `of=...`.

        Returns:
            QuerySet: A cloned queryset with locking enabled.
        """
        queryset: QuerySet = self._clone()
        payload: dict[str, Any] = {
            "nowait": bool(nowait),
            "skip_locked": bool(skip_locked),
            "read": bool(read),
            "key_share": bool(key_share),
        }
        if of:
            # Store model classes here during compilation we map them to actual (possibly aliased) tables
            payload["of"] = tuple(of)
        queryset._for_update = payload
        return queryset

    def filter(
        self,
        *clauses: sqlalchemy.sql.expression.BinaryExpression
        | Callable[
            [QuerySetType],
            sqlalchemy.sql.expression.BinaryExpression
            | Awaitable[sqlalchemy.sql.expression.BinaryExpression],
        ]
        | dict[str, Any]
        | QuerySet,
        **kwargs: Any,
    ) -> QuerySet:
        """
        Filters the QuerySet by the given clauses and keyword arguments, combining them with the AND operand.

        This is the primary method for constructing the WHERE clause of a query. Multiple clauses
        and kwargs are implicitly combined using AND.

        Args:
            *clauses: Positional arguments which can be:
                      - SQLAlchemy Binary Expressions (e.g., `Model.field == value`).
                      - Callables (sync/async) that accept the QuerySet and return a Binary Expression.
                      - Dictionaries (Django-style lookups, e.g., `{"field__gt": 10}`).
                      - Nested QuerySets (for subqueries).
            **kwargs: Keyword arguments for Django-style lookups (e.g., `field__gt=10`).

        Returns:
            A new QuerySet instance with the additional filters applied.
        """
        return self._filter_or_exclude(clauses=clauses, kwargs=kwargs)

    where = filter

    def all(self, clear_cache: bool = False) -> QuerySet:
        """
        Returns a cloned QuerySet instance, or simply clears the cache of the current instance.

        Args:
            clear_cache: If `True`, the method clears the internal cache and returns `self`.
                         If `False` (default), it returns a fresh clone with an empty cache.

        Returns:
            A new QuerySet clone or the current QuerySet instance (`self`).
        """
        if clear_cache:
            self._clear_cache(keep_cached_selected=not self._has_dynamic_clauses)
            return self
        return self._clone()

    def or_(
        self,
        *clauses: sqlalchemy.sql.expression.BinaryExpression
        | Callable[
            [QuerySetType],
            sqlalchemy.sql.expression.BinaryExpression
            | Awaitable[sqlalchemy.sql.expression.BinaryExpression],
        ]
        | dict[str, Any]
        | QuerySet,
        **kwargs: Any,
    ) -> QuerySet:
        """
        Filters the QuerySet by the given clauses and keyword arguments, combining them with the OR operand.

        This method is used to construct a disjunction (OR logic) for the WHERE clause.

        Args:
            *clauses: Positional arguments for filtering (same types as `filter`).
            **kwargs: Keyword arguments for filtering (Django-style lookups).

        Returns:
            A new QuerySet instance with the OR filters applied.
        """
        return self._filter_or_exclude(clauses=clauses, or_=True, kwargs=kwargs)

    def local_or(
        self,
        *clauses: sqlalchemy.sql.expression.BinaryExpression
        | Callable[
            [QuerySetType],
            sqlalchemy.sql.expression.BinaryExpression
            | Awaitable[sqlalchemy.sql.expression.BinaryExpression],
        ]
        | dict[str, Any]
        | QuerySet,
        **kwargs: Any,
    ) -> QuerySet:
        """
        Filters the QuerySet using the OR operand, but only applies the OR logic locally.

        This prevents the OR operation from becoming a global OR that overrides existing,
        unrelated AND filters, often by applying the OR clause within parentheses.

        Args:
            *clauses: Positional arguments for filtering.
            **kwargs: Keyword arguments for filtering.

        Returns:
            A new QuerySet instance with the local OR filters applied.
        """
        return self._filter_or_exclude(
            clauses=clauses, or_=True, kwargs=kwargs, allow_global_or=False
        )

    def and_(
        self,
        *clauses: sqlalchemy.sql.expression.BinaryExpression
        | Callable[
            [QuerySetType],
            sqlalchemy.sql.expression.BinaryExpression
            | Awaitable[sqlalchemy.sql.expression.BinaryExpression],
        ]
        | dict[str, Any],
        **kwargs: Any,
    ) -> QuerySet:
        """
        Filters the QuerySet by the given clauses and keyword arguments, using the AND operand.

        This method is an alias for `filter()`, explicitly stating the AND logic.

        Args:
            *clauses: Positional arguments for filtering.
            **kwargs: Keyword arguments for filtering.

        Returns:
            A new QuerySet instance with the AND filters applied.
        """
        return self._filter_or_exclude(clauses=clauses, kwargs=kwargs)

    def not_(
        self,
        *clauses: sqlalchemy.sql.expression.BinaryExpression
        | Callable[
            [QuerySetType],
            sqlalchemy.sql.expression.BinaryExpression
            | Awaitable[sqlalchemy.sql.expression.BinaryExpression],
        ]
        | dict[str, Any]
        | QuerySet,
        **kwargs: Any,
    ) -> QuerySet:
        """
        Excludes results from the QuerySet by negating the given clauses and keyword arguments.

        This method is an alias for `exclude()`, explicitly stating the NOT logic.

        Args:
            *clauses: Positional arguments for exclusion.
            **kwargs: Keyword arguments for exclusion.

        Returns:
            A new QuerySet instance with the exclusion applied.
        """
        return self.exclude(*clauses, **kwargs)

    def exclude(
        self,
        *clauses: sqlalchemy.sql.expression.BinaryExpression
        | Callable[
            [QuerySetType],
            sqlalchemy.sql.expression.BinaryExpression
            | Awaitable[sqlalchemy.sql.expression.BinaryExpression],
        ]
        | dict[str, Any]
        | QuerySet,
        **kwargs: Any,
    ) -> QuerySet:
        """
        Excludes results from the QuerySet by negating the given clauses and keyword arguments.

        The exclusion logic is typically implemented by calling `_filter_or_exclude`
        with the `exclude=True` flag.

        Args:
            *clauses: Positional arguments for exclusion (same types as `filter`).
            **kwargs: Keyword arguments for exclusion (Django-style lookups).

        Returns:
            A new QuerySet instance with the exclusion applied.
        """
        return self._filter_or_exclude(clauses=clauses, exclude=True, kwargs=kwargs)

    def exclude_secrets(
        self,
        exclude_secrets: bool = True,
    ) -> QuerySet:
        """
        Marks the QuerySet to exclude any model fields declared with `secret=True` from being leaked
        or serialized in the final result set.

        Args:
            exclude_secrets: If `True` (default), secrets are excluded; if `False`, they are included.

        Returns:
            A new QuerySet clone with the `_exclude_secrets` flag set.
        """
        queryset = self._clone()
        queryset._exclude_secrets = exclude_secrets
        return queryset

    def extra_select(
        self,
        *extra: sqlalchemy.ColumnClause,
    ) -> QuerySetType:
        """
        Adds extra columns or expressions to the SELECT statement.

        Args:
            *extra (sqlalchemy.ColumnClause): Additional SQLAlchemy column clauses or expressions.

        Returns:
            QuerySetType: A new QuerySet with the extra select clauses.
        """
        queryset = self._clone()
        queryset._extra_select.extend(extra)
        return queryset

    def reference_select(self, references: reference_select_type) -> QuerySetType:
        """
        Adds references to the SELECT statement, used for specific model field handling.

        Args:
            references (reference_select_type): A dictionary defining reference selections.

        Returns:
            QuerySetType: A new QuerySet with the added reference selections.
        """
        queryset = self._clone()
        queryset._reference_select.update(references)
        return queryset

    def batch_size(
        self,
        batch_size: int | None = None,
    ) -> QuerySet:
        """
        Sets the batch or chunk size for results. This is primarily used in conjunction
        with iteration methods (like `QuerySet.iterate()`) to control memory usage.

        Args:
            batch_size: The number of records to fetch in each database round-trip.
                        If `None`, iteration may fetch all results at once (depending on the backend).

        Returns:
            A new QuerySet clone with the batch size set.
        """
        queryset = self._clone()
        queryset._batch_size = batch_size
        return queryset

    def lookup(self, term: Any) -> QuerySet:
        """
        Performs a broader, case-insensitive search for a given term across all
        CharField and TextField instances defined on the model.

        The search uses the SQL `LIKE` operator with wildcards (`%`) and typically
        maps to `ILIKE` on PostgreSQL for case-insensitivity.

        Args:
            term: The search term to look for.

        Returns:
            A new QuerySet instance with the combined OR filter applied to all searchable fields.
        """
        queryset: QuerySet = self._clone()
        if not term:
            return queryset

        filter_clauses = list(queryset.filter_clauses)
        value = f"%{term}%"

        search_fields = [
            name
            for name, field in queryset.model_class.meta.fields.items()
            if isinstance(field, CharField | TextField)
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

        Sorting is applied in ascending order by default. Prepending a field name with
        a hyphen (`-`) specifies descending order (e.g., `-created_at`).

        Args:
            *order_by: One or more field names to sort by.

        Returns:
            A new QuerySet clone with the specified ordering.
        """
        queryset: QuerySet = self._clone()
        queryset._order_by = order_by
        if queryset._update_select_related_weak(order_by, clear=True):
            queryset._update_select_related_weak(queryset._group_by, clear=False)
        return queryset

    def reverse(self) -> QuerySet:
        """
        Reverses the established order of the QuerySet.

        If an `order_by` is already set, it negates the sorting direction of every field.
        If no `order_by` is set, it defaults to reversing the primary key columns.
        It also adjusts internal cache pointers for consistency if caching is active.

        Returns:
            A new QuerySet clone with the reversed ordering.
        """
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
            # we may have embedded active
            cache_keys = []
            values = []
            for k, v in reversed(self._cache.get_category(self.model_class).items()):
                cache_keys.append(k)
                values.append(v)
            queryset._cache.update(self.model_class, values, cache_keys=cache_keys)
            queryset._cache_fetch_all = True
        return queryset

    def limit(self, limit_count: int) -> QuerySet:
        """
        Limits the number of results returned by the QuerySet (SQL LIMIT clause).

        Args:
            limit_count: The maximum number of rows to return.

        Returns:
            A new QuerySet clone with the limit applied.
        """
        queryset: QuerySet = self._clone()
        queryset.limit_count = limit_count
        return queryset

    def offset(self, offset: int) -> QuerySet:
        """
        Skips the specified number of results before starting to return rows (SQL OFFSET clause).

        Args:
            offset: The number of rows to skip.

        Returns:
            A new QuerySet clone with the offset applied.
        """
        queryset: QuerySet = self._clone()
        queryset._offset = offset
        return queryset

    def group_by(self, *group_by: str) -> QuerySet:
        """
        Groups the results of the QuerySet by the given fields (SQL GROUP BY clause).

        Args:
            *group_by: One or more field names to group the results by.

        Returns:
            A new QuerySet clone with the grouping applied.
        """
        queryset: QuerySet = self._clone()
        queryset._group_by = group_by
        if queryset._update_select_related_weak(group_by, clear=True):
            queryset._update_select_related_weak(queryset._order_by, clear=False)
        return queryset

    def distinct(self, first: bool | str = True, *distinct_on: str) -> QuerySet:
        """
        Returns a queryset with distinct results.

        Args:
            first (bool | str): If True, applies `DISTINCT`. If False, removes any distinct clause.
                                If a string, applies `DISTINCT ON` to that field.
            *distinct_on (str): Additional fields for `DISTINCT ON`.

        Returns:
            QuerySet: A new QuerySet with the distinct clause applied.
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
        Restricts the QuerySet to retrieve **only** the specified fields from the database
        for the model instances, along with the primary key field(s).

        This method is used for performance optimization when only a subset of columns is needed.
        The primary key is automatically included to ensure object identity and saving functionality.

        Args:
            *fields: The names of the model fields (columns) to include in the SELECT statement.

        Returns:
            A new QuerySet clone with the `_only` set attribute containing the selected fields.
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
        Excludes the specified fields from being retrieved from the database.

        When accessing a deferred field on a model instance, a subsequent database query
        will be triggered to fetch its value. This is useful for large, rarely accessed
        fields (e.g., large text blobs).

        Args:
            *fields: The names of the model fields (columns) to **exclude** from the SELECT statement.

        Returns:
            A new QuerySet clone with the `_defer` set attribute containing the fields to skip.
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
        queryset._update_select_related(related)
        return queryset

    async def values(
        self,
        fields: Sequence[str] | str | None = None,
        exclude: Sequence[str] | set[str] = None,
        exclude_none: bool = False,
    ) -> list[dict]:
        """
        Executes the query and returns the results as a list of Python dictionaries,
        rather than model instances.

        Args:
            fields: A sequence of field names to include in the resulting dictionaries.
                    If `None`, all model fields are included.
            exclude: A sequence of field names to exclude from the resulting dictionaries.
            exclude_none: If `True`, fields with a value of `None` are omitted from the dictionaries.

        Returns:
            A list of dictionaries representing the selected data rows.

        Raises:
            QuerySetError: If the `fields` argument is not a suitable sequence.
        """

        if isinstance(fields, str):
            fields = [fields]

        if fields is not None and not isinstance(fields, Iterable):
            raise QuerySetError(detail="Fields must be a suitable sequence of strings or unset.")

        rows: list[BaseModelType] = await self
        if fields:
            return [
                row.model_dump(exclude=exclude, exclude_none=exclude_none, include=fields)
                for row in rows
            ]
        else:
            return [row.model_dump(exclude=exclude, exclude_none=exclude_none) for row in rows]

    async def values_list(
        self,
        fields: Sequence[str] | str | None = None,
        exclude: Sequence[str] | set[str] = None,
        exclude_none: bool = False,
        flat: bool = False,
    ) -> list[Any]:
        """
        Executes the query and returns the results as a list of tuples or, if `flat=True`,
        a flat list of values for a single field.

        Args:
            fields: A sequence of field names to include. Must contain exactly one field if `flat=True`.
            exclude: A sequence of field names to exclude.
            exclude_none: If `True`, fields with a value of `None` are omitted during dictionary creation.
            flat: If `True` and only one field is selected, returns a list of values instead of tuples/dictionaries.

        Returns:
            A list of tuples, or a flat list of values if `flat=True`.

        Raises:
            QuerySetError: If `flat=True` but more than one field is selected, or if the selected field does not exist.
        """
        if isinstance(fields, str):
            fields = [fields]
        rows = await self.values(
            fields=fields,
            exclude=exclude,
            exclude_none=exclude_none,
        )
        if not rows:
            return []
        if not flat:
            return [tuple(row.values()) for row in rows]
        else:
            try:
                return [row[fields[0]] for row in rows]
            except KeyError:
                raise QuerySetError(detail=f"{fields[0]} does not exist in the results.") from None

    async def exists(self, **kwargs: Any) -> bool:
        """
        Returns a boolean indicating if one or more records matching the QuerySet's criteria exists.

        If keyword arguments are provided, it first checks the cache for an existence match.

        Args:
            **kwargs: Optional filters to apply before checking for existence (e.g., `pk=1`).

        Returns:
            True if at least one record exists, False otherwise.
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
        Executes a SELECT COUNT statement and returns the total number of records matching the query.

        The result is cached internally to prevent redundant database calls for subsequent counts.

        For queries that may produce duplicate rows at the SQL level
        (e.g. OR across joined relations, select_related joins, GROUP BY),
        this method counts DISTINCT primary keys to reflect the number of
        unique model instances rather than raw joined rows.
        """
        if self._cache_count is not None:
            return self._cache_count

        queryset: QuerySet = self

        needs_distinct = (
            bool(queryset.or_clauses) or bool(queryset._select_related) or bool(queryset._group_by)
        )

        base_select = await queryset.as_select()
        subquery = base_select.subquery("subquery_for_count")

        # Build COUNT expression
        if needs_distinct:
            # Support composite primary keys if present
            pk_cols = [subquery.c[col] for col in queryset.model_class.pkcolumns]
            if len(pk_cols) == 1:
                count_expr = sqlalchemy.func.count(sqlalchemy.distinct(pk_cols[0]))
            else:
                # DISTINCT over a tuple of PK columns
                count_expr = sqlalchemy.func.count(
                    sqlalchemy.distinct(sqlalchemy.tuple_(*pk_cols))
                )
            count_query = sqlalchemy.select(count_expr)
        else:
            # Simple COUNT(*) over the subquery
            count_query = sqlalchemy.select(sqlalchemy.func.count()).select_from(subquery)

        check_db_connection(queryset.database)
        async with queryset.database as database:
            self._cache_count = count = cast(int, await database.fetch_val(count_query))
        return count

    total = count

    async def get_or_none(self, **kwargs: Any) -> EdgyEmbedTarget | None:
        """
        Fetches a single object matching the parameters.

        If no object is found (raises `ObjectNotFound`), returns `None`.

        Args:
            **kwargs: Filters to identify the single object.

        Returns:
            The matching model instance, or `None`.
        """
        try:
            return await self.get(**kwargs)
        except ObjectNotFound:
            return None

    select_or_none = get_or_none

    async def get(self, **kwargs: Any) -> EdgyEmbedTarget:
        """
        Fetches a single object matching the parameters.

        Args:
            **kwargs: Filters to identify the single object.

        Returns:
            The matching model instance.

        Raises:
            ObjectNotFound: If no object is found.
            MultipleObjectsReturned: If more than one object is found (implicitly handled by underlying `_get_raw`).
        """
        return cast(EdgyEmbedTarget, (await self._get_raw(**kwargs))[1])

    select = get

    async def first(self) -> EdgyEmbedTarget | None:
        """
        Returns the first record from the QuerySet, respecting any ordering and limits.

        If the count is zero or the first record is already cached, it returns the cached result.

        Returns:
            The first model instance, or `None` if the QuerySet is empty.
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
            parser = ResultParser(self)
            result_tuple: tuple[Any, EdgyEmbedTarget] = await parser.row_to_model(
                row, tables_and_models
            )
            self._cache_first = result_tuple
            return result_tuple[1]
        return None

    async def last(self) -> EdgyEmbedTarget | None:
        """
        Returns the last record from the QuerySet...
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
            # NEW FIXED LINES:
            parser = ResultParser(self)
            result_tuple: tuple[Any, EdgyEmbedTarget] = await parser.row_to_model(
                row, tables_and_models
            )
            self._cache_last = result_tuple
            return result_tuple[1]
        return None

    async def create(self, *args: Any, **kwargs: Any) -> EdgyEmbedTarget:
        """
        Creates and saves a single record in the database table associated with the QuerySet's model.

        Args:
            *args: Positional arguments for model instantiation.
            **kwargs: Keyword arguments for model instantiation and field values.

        Returns:
            The newly created model instance.
        """
        # for tenancy
        queryset: QuerySet = self._clone()
        check_db_connection(queryset.database)
        token = CHECK_DB_CONNECTION_SILENCED.set(True)
        try:
            instance = queryset.model_class(*args, **kwargs)
            # apply_instance_extras filters out table Alias
            apply_instance_extras(
                instance,
                self.model_class,
                schema=self.using_schema,
                table=queryset.table,
                database=queryset.database,
            )
            # values=set(kwargs.keys()) is required for marking the provided kwargs as explicit provided kwargs
            token2 = CURRENT_INSTANCE.set(self)
            try:
                instance = await instance.real_save(force_insert=True, values=set(kwargs.keys()))
            finally:
                CURRENT_INSTANCE.reset(token2)
            result = await self._embed_parent_in_result(instance)
            self._clear_cache(keep_result_cache=True)
            self._cache.update(
                self.model_class,
                [result],
                cache_keys=[self._cache.create_cache_key(self.model_class, result[0])],
            )
            return cast(EdgyEmbedTarget, result[1])
        finally:
            CHECK_DB_CONNECTION_SILENCED.reset(token)

    insert = create

    async def bulk_create(self, objs: Iterable[dict[str, Any] | EdgyModel]) -> None:
        """
        Bulk creates multiple records in a single batch operation.

        This method bypasses model-level save hooks (except for pre/post-save) for efficiency,
        and returns `None`.

        Args:
            objs: An iterable of dictionaries or model instances to be created.
        """
        queryset: QuerySet = self._clone()

        new_objs: list[EdgyModel] = []

        async def _iterate(obj_or_dict: EdgyModel | dict[str, Any]) -> dict[str, Any]:
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
                original,
                phase="prepare_insert",
                instance=self,
                model_instance=obj,
            )
            col_values.update(
                await obj.execute_pre_save_hooks(col_values, original, is_update=False)
            )
            return col_values

        check_db_connection(queryset.database)
        token = CURRENT_INSTANCE.set(self)
        try:
            async with queryset.database as database, database.transaction():
                obj_values = [await _iterate(obj) for obj in objs]
                # early bail out if no objects were found. This prevents issues with the db
                if not obj_values:
                    return
                expression = queryset.table.insert().values(obj_values)
                await database.execute_many(expression)
            self._clear_cache(keep_result_cache=True)
            if new_objs:
                keys = self.model_class.meta.fields.keys()
                await run_concurrently(
                    [obj.execute_post_save_hooks(keys, is_update=False) for obj in new_objs],
                    limit=(1 if getattr(queryset.database, "force_rollback", False) else None),
                )
        finally:
            CURRENT_INSTANCE.reset(token)

    bulk_insert = bulk_create

    async def bulk_update(self, objs: list[EdgyModel], fields: list[str]) -> None:
        """
        Bulk updates records in a table based on the provided list of model instances and fields.

        The primary key of each model instance is used to identify the record to update.
        This operation is performed within a database transaction.

        Args:
            objs: A list of existing model instances to update.
            fields: A list of field names that should be updated across all instances.
        """
        fields = list(fields)
        # we can't update anything without fields
        if not fields:
            return
        queryset: QuerySet = self._clone()

        pk_query_placeholder = (
            getattr(queryset.table.c, pkcol)
            == sqlalchemy.bindparam(
                "__id" if pkcol == "id" else pkcol,
                type_=getattr(queryset.table.c, pkcol).type,
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
                        await obj.execute_pre_save_hooks(update, extracted, is_update=True)
                    )
                    if "id" in update:
                        update["__id"] = update.pop("id")
                    update_list.append(update)
                # prevent calling db with empty iterable, this causes errors
                if not update_list:
                    return

                values_placeholder: dict[str, Any] = {
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
                await run_concurrently(
                    [obj.execute_post_save_hooks(fields, is_update=True) for obj in objs],
                    limit=(1 if getattr(queryset.database, "force_rollback", False) else None),
                )
        finally:
            CURRENT_INSTANCE.reset(token)

    async def bulk_get_or_create(
        self,
        objs: list[dict[str, Any] | EdgyModel],
        unique_fields: list[str] | None = None,
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
                # This fixes edgy-guardian bug when using databasez.iterate indirectly and
                # is safe in case force_rollback is active
                # Models can also issue loads by accessing attrs for building unique_fields
                # For limiting use something like QuerySet.limit(100).bulk_get_or_create(...)
                for model in await queryset.filter(**filter_kwargs):
                    if all(getattr(model, k) == expected for k, expected in dict_fields.items()):
                        lookup_key = _extract_unique_lookup_key(model, unique_fields)
                        assert lookup_key is not None, "invalid fields/attributes in unique_fields"
                        if lookup_key not in existing_records:
                            existing_records[lookup_key] = model
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
                await obj.execute_pre_save_hooks(col_values, original, is_update=False)
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
                keys = self.model_class.meta.fields.keys()
                await run_concurrently(
                    [obj.execute_post_save_hooks(keys, is_update=False) for obj in new_objs],
                    limit=(1 if getattr(queryset.database, "force_rollback", False) else None),
                )
        finally:
            CURRENT_INSTANCE.reset(token)

        return retrieved_objs

    bulk_select_or_insert = bulk_get_or_create

    async def delete(self, use_models: bool = False) -> int:
        """
        Deletes records from the database.

        This method triggers `pre_delete` and `post_delete` signals.
        If `use_models` is True or the model has specific deletion requirements,
        it performs a model-based deletion.

        Args:
            use_models (bool): If True, deletion is performed by iterating and
                               deleting individual model instances. Defaults to False.

        Returns:
            int: The number of rows deleted.
        """
        await self.model_class.meta.signals.pre_delete.send_async(
            self.model_class, instance=self, model_instance=None
        )
        row_count = await self.raw_delete(use_models=use_models, remove_referenced_call=False)
        await self.model_class.meta.signals.post_delete.send_async(
            self.model_class, instance=self, model_instance=None, row_count=row_count
        )
        return row_count

    async def update(self, **kwargs: Any) -> None:
        """
        Updates records in a specific table with the given keyword arguments, matching the QuerySet's filters.

        This performs a database-level update operation without fetching and saving model instances.

        Warning:
        - **Does not** execute instance-level `pre_save_callback`/`post_save_callback` hooks.
        - Values are processed directly for column mapping and validation but do not pass through model instance saving.

        Args:
            **kwargs: The field names and new values to apply to the matching records.
        """

        column_values = self.model_class.extract_column_values(
            kwargs,
            is_update=True,
            is_partial=True,
            phase="prepare_update",
            instance=self,
        )

        # Broadcast the initial update details
        # add is_update to match save
        await self.model_class.meta.signals.pre_update.send_async(
            self.model_class,
            instance=self,
            model_instance=None,
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
            model_instance=None,
            values=kwargs,
            column_values=column_values,
            is_update=True,
            is_migration=False,
        )
        self._clear_cache()

    async def get_or_create(
        self, defaults: dict[str, Any] | Any | None = None, *args: Any, **kwargs: Any
    ) -> tuple[EdgyEmbedTarget, bool]:
        """
        Fetches a single object matching `kwargs`. If found, returns the object and `False`.
        If not found, creates a new object using `kwargs` (with `defaults` applied) and returns it with `True`.

        Args:
            defaults: Optional dictionary of values to use if a new object must be created.
                      Can also be a `ModelRef` instance to set a related object upon creation.
            *args: Positional arguments for model creation if object is not found.
            **kwargs: Filters used to attempt retrieval, and primary creation arguments if not found.

        Returns:
            A tuple containing the fetched/created model instance and a boolean indicating
            if the object was created (`True`) or fetched (`False`).
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

    select_or_insert = get_or_create

    async def update_or_create(
        self, defaults: dict[str, Any] | Any | None = None, *args: Any, **kwargs: Any
    ) -> tuple[EdgyEmbedTarget, bool]:
        """
        Updates a single object matching `kwargs` using `defaults`. If not found, creates a new object.

        Args:
            defaults: Optional dictionary of values to apply as updates if the object is found,
                      or to use as creation values if the object is new. Can also be a `ModelRef`.
            *args: Positional arguments for model creation if object is not found.
            **kwargs: Filters used to attempt retrieval.

        Returns:
            A tuple containing the fetched/created model instance and a boolean indicating
            if the object was created (`True`) or updated (`False`).
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

    update_or_insert = update_or_create

    async def contains(self, instance: BaseModelType) -> bool:
        """
        Checks if the QuerySet contains a specific model instance by verifying its existence
        in the database using its primary key(s).

        Args:
            instance: The model instance to check for containment.

        Returns:
            True if the record exists in the database and matches the QuerySet filters, False otherwise.

        Raises:
            ValueError: If the provided object is not a model instance or has a missing primary key.
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

    like = contains

    def transaction(self, *, force_rollback: bool = False, **kwargs: Any) -> Transaction:
        """
        Returns a database transaction context manager for the assigned database.

        Args:
            force_rollback: If `True`, the transaction will always rollback when the context manager exits,
                            regardless of whether an exception occurred. Useful for testing.
            **kwargs: Additional keyword arguments passed to the underlying database transaction factory.

        Returns:
            A `Transaction` context manager.
        """
        return self.database.transaction(force_rollback=force_rollback, **kwargs)

    def __await__(
        self,
    ) -> Generator[Any, None, list[Any]]:
        return self._execute_all().__await__()

    async def __aiter__(self) -> AsyncIterator[Any]:
        async for value in self._execute_iterate():
            yield value
