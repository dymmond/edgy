import asyncio
import copy
import warnings
from inspect import isawaitable
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncIterator,
    Awaitable,
    Dict,
    Generator,
    List,
    Optional,
    Sequence,
    Set,
    Tuple,
    Type,
    Union,
    cast,
)

import sqlalchemy

from edgy.conf import settings
from edgy.core.db.context_vars import get_schema
from edgy.core.db.fields import CharField, TextField
from edgy.core.db.fields.base import BaseForeignKey, RelationshipField
from edgy.core.db.models.mixins import ModelParser
from edgy.core.db.querysets.mixins import EdgyModel, QuerySetPropsMixin, TenancyMixin
from edgy.core.db.querysets.prefetch import PrefetchMixin
from edgy.core.db.querysets.protocols import AwaitableQuery
from edgy.core.db.relationships.utils import crawl_relationship
from edgy.exceptions import MultipleObjectsReturned, ObjectNotFound, QuerySetError
from edgy.protocols.queryset import QuerySetProtocol

from . import clauses as clauses_mod

if TYPE_CHECKING:  # pragma: no cover
    from edgy import Database
    from edgy.core.db.models import Model


def clean_query_kwargs(model: Type["Model"], kwargs: Dict[str, Any]) -> Dict[str, Any]:
    new_kwargs: Dict[str, Any] = {}
    for key, val in kwargs.items():
        model_class, field_name, _, _, _ = crawl_relationship(model, key)
        field = model_class.meta.fields.get(field_name)
        if field is not None:
            new_kwargs.update(field.clean(key, val, for_query=True))
        else:
            new_kwargs[key] = val
    assert "pk" not in new_kwargs, "pk should be already parsed"
    return new_kwargs


class BaseQuerySet(
    TenancyMixin,
    QuerySetPropsMixin,
    PrefetchMixin,
    ModelParser,
    AwaitableQuery[EdgyModel],
):
    ESCAPE_CHARACTERS = ["%", "_"]

    def __init__(
        self,
        model_class: Union[Type["Model"], None] = None,
        database: Union["Database", None] = None,
        filter_clauses: Any = None,
        or_clauses: Any = None,
        select_related: Any = None,
        prefetch_related: Any = None,
        limit_count: Any = None,
        limit_offset: Any = None,
        order_by: Any = None,
        group_by: Any = None,
        distinct_on: Optional[Sequence[str]] = None,
        only_fields: Any = None,
        defer_fields: Any = None,
        embed_parent: Any = None,
        using_schema: Any = None,
        table: Any = None,
        exclude_secrets: Any = False,
    ) -> None:
        super().__init__(model_class=model_class)
        self.model_class = cast("Type[Model]", model_class)
        self.filter_clauses = [] if filter_clauses is None else filter_clauses
        self.or_clauses = [] if or_clauses is None else or_clauses
        self.limit_count = limit_count
        self._select_related = [] if select_related is None else select_related
        self._prefetch_related = [] if prefetch_related is None else prefetch_related
        self._offset = limit_offset
        self._order_by = [] if order_by is None else order_by
        self._group_by = [] if group_by is None else group_by
        self.distinct_on = distinct_on
        self._only = [] if only_fields is None else only_fields
        self._defer = [] if defer_fields is None else defer_fields
        self._expression = None
        self._cache = None
        self.embed_parent = embed_parent
        self.using_schema = using_schema
        self._exclude_secrets = exclude_secrets or False

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

    def _build_filter_clauses_expression(self, filter_clauses: Any, expression: Any) -> Any:
        """Builds the filter clauses expression"""
        if len(filter_clauses) == 1:
            clause = filter_clauses[0]
        else:
            clause = clauses_mod.and_(*filter_clauses)
        expression = expression.where(clause)
        return expression

    def _build_or_clauses_expression(self, or_clauses: Any, expression: Any) -> Any:
        """Builds the filter clauses expression"""
        clause = or_clauses[0] if len(or_clauses) == 1 else clauses_mod.or_(*or_clauses)
        expression = expression.where(clause)
        return expression

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
                if foreign_key.is_cross_db():
                    raise NotImplementedError(
                        "We cannot cross databases yet, this feature is planned"
                    )
                table = model_class.table
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
        self, model_class: Any, columns: Union[List[str], None] = None
    ) -> List[str]:
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

    def _build_select(self) -> Any:
        """
        Builds the query select based on the given parameters and filters.
        """
        queryset: QuerySet = self._clone()

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

        if queryset.filter_clauses:
            expression = queryset._build_filter_clauses_expression(
                queryset.filter_clauses, expression=expression
            )

        if queryset.or_clauses:
            expression = queryset._build_or_clauses_expression(
                queryset.or_clauses, expression=expression
            )

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

        queryset._expression = expression  # type: ignore
        return expression

    def _filter_query(
        self,
        kwargs: Any,
        exclude: bool = False,
        or_: bool = False,
    ) -> "QuerySet":
        from edgy.core.db.models import Model

        clauses = []
        filter_clauses = self.filter_clauses
        or_clauses = self.or_clauses
        select_related = list(self._select_related)
        prefetch_related = list(self._prefetch_related)

        # Making sure for queries we use the main class and not the proxy
        # And enable the parent
        if self.model_class.__is_proxy_model__:
            self.model_class = self.model_class.__parent__

        kwargs = clean_query_kwargs(self.model_class, kwargs)

        for key, value in kwargs.items():
            assert not isinstance(value, Model), f"should be parsed in clean: {key}: {value}"
            model_class, field_name, op, related_str, _ = crawl_relationship(self.model_class, key)
            if related_str and related_str not in select_related:
                select_related.append(related_str)
            column = model_class.table.columns[field_name]

            # Map the operation code onto SQLAlchemy's ColumnElement
            # https://docs.sqlalchemy.org/en/latest/core/sqlelement.html#sqlalchemy.sql.expression.ColumnElement
            op_attr = settings.filter_operators[op]
            has_escaped_character = False

            if op in ["contains", "icontains"]:
                has_escaped_character = any(c for c in self.ESCAPE_CHARACTERS if c in value)
                if has_escaped_character:
                    # enable escape modifier
                    for char in self.ESCAPE_CHARACTERS:
                        value = value.replace(char, f"\\{char}")
                value = f"%{value}%"

            clause = getattr(column, op_attr)(value)
            clause.modifiers["escape"] = "\\" if has_escaped_character else None
            clauses.append(clause)

        if exclude:
            if not or_:
                filter_clauses.append(clauses_mod.not_(clauses_mod.and_(*clauses)))
            else:
                or_clauses.append(clauses_mod.not_(clauses_mod.and_(*clauses)))
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
                order_by=self._order_by,
                only_fields=self._only,
                defer_fields=self._defer,
                embed_parent=self.embed_parent,
                table=self.table,
                exclude_secrets=self._exclude_secrets,
                using_schema=self.using_schema,
            ),
        )

    def _validate_kwargs(self, **kwargs: Any) -> Any:
        return self.extract_column_values(kwargs, model_class=self.model_class)

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

    def _clone(self) -> "QuerySet":
        """
        Return a copy of the current QuerySet that's ready for another
        operation.
        """
        queryset = self.__class__.__new__(self.__class__)
        queryset.model_class = self.model_class

        # Making sure the registry schema takes precendent with
        # Any provided using
        if not self.model_class.meta.registry.db_schema:
            schema = get_schema()
            if self.using_schema is None and schema is not None:
                self.using_schema = schema
            queryset.model_class.table = self.model_class.build(self.using_schema)

        queryset.filter_clauses = copy.copy(self.filter_clauses)
        queryset.or_clauses = copy.copy(self.or_clauses)
        queryset.limit_count = copy.copy(self.limit_count)
        queryset._select_related = copy.copy(self._select_related)
        queryset._prefetch_related = copy.copy(self._prefetch_related)
        queryset._offset = copy.copy(self._offset)
        queryset._order_by = copy.copy(self._order_by)
        queryset._group_by = copy.copy(self._group_by)
        queryset.distinct_on = copy.copy(self.distinct_on)
        queryset._expression = copy.copy(self._expression)
        queryset.embed_parent = self.embed_parent
        queryset._only = copy.copy(self._only)
        queryset._defer = copy.copy(self._defer)
        queryset._database = self.database
        queryset.table = self.table
        queryset._exclude_secrets = self._exclude_secrets
        queryset.using_schema = self.using_schema

        return cast("QuerySet", queryset)


class QuerySet(BaseQuerySet, QuerySetProtocol):
    """
    QuerySet object used for query retrieving.
    """

    def __get__(self, instance: Any, owner: Any = None) -> "QuerySet":
        return self.__class__(model_class=owner if owner else instance.__class__)

    @property
    def sql(self) -> Any:
        return self._expression

    @sql.setter
    def sql(self, value: Any) -> None:
        self._expression = value

    def _set_query_expression(self, expression: Any) -> None:
        """
        Sets the value of the sql property to the expression used.
        """
        self.sql = expression
        self.model_class.raw_query = self.sql

    def _filter_or_exclude(
        self,
        kwargs: Any,
        clauses: Sequence[sqlalchemy.sql.expression.BinaryExpression],
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

    def filter(
        self,
        *clauses: Tuple[sqlalchemy.sql.expression.BinaryExpression, ...],
        **kwargs: Any,
    ) -> "QuerySet":
        """
        Filters the QuerySet by the given kwargs and clauses.
        """
        return self._filter_or_exclude(clauses=clauses, kwargs=kwargs)

    def all(self, **kwargs: Any) -> "QuerySet":
        """
        Returns the queryset records based on specific filters
        """
        # filter with reduced functionality
        return self.filter(**kwargs) if kwargs else self._clone()

    def or_(
        self,
        *clauses: Tuple[sqlalchemy.sql.expression.BinaryExpression, ...],
        **kwargs: Any,
    ) -> "QuerySet":
        """
        Filters the QuerySet by the OR operand.
        """
        return self._filter_or_exclude(clauses=clauses, or_=True, kwargs=kwargs)

    def and_(
        self,
        *clauses: Tuple[sqlalchemy.sql.expression.BinaryExpression, ...],
        **kwargs: Any,
    ) -> "QuerySet":
        """
        Filters the QuerySet by the AND operand. Alias of filter.
        """
        return self.filter(*clauses, **kwargs)

    def not_(
        self,
        *clauses: Tuple[sqlalchemy.sql.expression.BinaryExpression, ...],
        **kwargs: Any,
    ) -> "QuerySet":
        """
        Filters the QuerySet by the NOT operand. Alias of exclude.
        """
        return self.exclude(*clauses, **kwargs)

    def exclude(
        self,
        *clauses: Tuple[sqlalchemy.sql.expression.BinaryExpression, ...],
        **kwargs: Any,
    ) -> "QuerySet":
        """
        Exactly the same as the filter but for the exclude.
        """
        return self._filter_or_exclude(clauses=clauses, exclude=True, kwargs=kwargs)

    def exclude_secrets(
        self,
        *clauses: Tuple[sqlalchemy.sql.expression.BinaryExpression, ...],
        **kwargs: Any,
    ) -> "QuerySet":
        """
        Excludes any field that contains the `secret=True` declared from being leaked.
        """
        queryset = self.filter(*clauses, **kwargs)
        queryset._exclude_secrets = True
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

    def only(self, *fields: Sequence[str]) -> "QuerySet":
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
        exclude: Union[Sequence[str], Set[str]] = None,
        exclude_none: bool = False,
        flatten: bool = False,
        **kwargs: Any,
    ) -> List[Any]:
        """
        Returns the results in a python dictionary format.
        """
        fields = fields or []
        queryset: QuerySet = self._clone()
        rows: List[Model] = await queryset.all()

        if not isinstance(fields, list):
            raise QuerySetError(detail="Fields must be an iterable.")

        if not fields:
            rows = [row.model_dump(exclude=exclude, exclude_none=exclude_none) for row in rows]
        else:
            rows = [
                row.model_dump(exclude=exclude, exclude_none=exclude_none, include=fields)
                for row in rows
            ]

        as_tuple = kwargs.pop("__as_tuple__", False)

        if not as_tuple:
            return rows

        if not flatten:
            rows = [tuple(row.values()) for row in rows]  # type: ignore
        else:
            try:
                rows = [row[fields[0]] for row in rows]  # type: ignore
            except KeyError:
                raise QuerySetError(detail=f"{fields[0]} does not exist in the results.") from None
        return rows

    async def values_list(
        self,
        fields: Union[Sequence[str], str, None] = None,
        exclude: Union[Sequence[str], Set[str]] = None,
        exclude_none: bool = False,
        flat: bool = False,
    ) -> List[Any]:
        """
        Returns the results in a python dictionary format.
        """
        queryset: QuerySet = self._clone()
        fields = fields or []
        if flat and len(fields) > 1:
            raise QuerySetError(
                detail=f"Maximum of 1 in fields when `flat` is enables, got {len(fields)} instead."
            ) from None

        if flat and isinstance(fields, str):
            fields = [fields]

        if isinstance(fields, str):
            fields = [fields]

        return await queryset.values(
            fields=fields,
            exclude=exclude,
            exclude_none=exclude_none,
            flatten=flat,
            __as_tuple__=True,
        )

    async def exists(self, **kwargs: Any) -> bool:
        """
        Returns a boolean indicating if a record exists or not.
        """
        queryset: QuerySet = self._clone()
        expression = queryset._build_select()
        expression = sqlalchemy.exists(expression).select()
        queryset._set_query_expression(expression)
        _exists = await queryset.database.fetch_val(expression)
        return cast("bool", _exists)

    async def count(self, **kwargs: Any) -> int:
        """
        Returns an indicating the total records.
        """
        queryset: QuerySet = self._clone()
        expression = queryset._build_select().alias("subquery_for_count")
        expression = sqlalchemy.func.count().select().select_from(expression)
        queryset._set_query_expression(expression)
        _count = await queryset.database.fetch_val(expression)
        return cast("int", _count)

    async def get_or_none(self, **kwargs: Any) -> Union[EdgyModel, None]:
        """
        Fetch one object matching the parameters or returns None.
        """
        queryset: QuerySet = self.filter(**kwargs)
        expression = queryset._build_select().limit(2)
        queryset._set_query_expression(expression)
        rows = await queryset.database.fetch_all(expression)

        if not rows:
            return None
        if len(rows) > 1:
            raise MultipleObjectsReturned()
        return await self.embed_parent_in_result(
            await queryset.model_class.from_sqla_row(
                rows[0],
                select_related=queryset._select_related,
                exclude_secrets=queryset._exclude_secrets,
                using_schema=queryset.using_schema,
            )
        )

    async def embed_parent_in_result(self, result: Any) -> Any:
        if isawaitable(result):
            result = await result
        if not self.embed_parent:
            return result
        new_result = result
        for part in self.embed_parent[0].split("__"):
            if hasattr(new_result, "_return_load_coro_on_attr_access"):
                new_result._return_load_coro_on_attr_access = True
            new_result = getattr(new_result, part)
            if isawaitable(new_result):
                new_result = await new_result
        if self.embed_parent[1]:
            setattr(new_result, self.embed_parent[1], result)
        return new_result

    async def get(self, **kwargs: Any) -> EdgyModel:
        """
        Returns a single record based on the given kwargs.
        """

        if kwargs:
            return await self.filter(**kwargs).get()

        queryset: QuerySet = self._clone()

        expression = queryset._build_select().limit(2)
        rows = await queryset.database.fetch_all(expression)
        queryset._set_query_expression(expression)

        is_only_fields = bool(queryset._only)
        is_defer_fields = bool(queryset._defer)

        if not rows:
            raise ObjectNotFound()
        if len(rows) > 1:
            raise MultipleObjectsReturned()

        return await self.embed_parent_in_result(
            queryset.model_class.from_sqla_row(
                rows[0],
                select_related=queryset._select_related,
                is_only_fields=is_only_fields,
                only_fields=queryset._only,
                is_defer_fields=is_defer_fields,
                prefetch_related=queryset._prefetch_related,
                exclude_secrets=queryset._exclude_secrets,
                using_schema=queryset.using_schema,
            )
        )

    async def first(self, **kwargs: Any) -> Union[EdgyModel, None]:
        """
        Returns the first record of a given queryset.
        """
        queryset: QuerySet = self._clone()
        if kwargs:
            return await queryset.filter(**kwargs).order_by("id").get()

        rows = await queryset.limit(1).order_by("id").all()
        if rows:
            return await self.embed_parent_in_result(rows[0])
        return None

    async def last(self, **kwargs: Any) -> Union[EdgyModel, None]:
        """
        Returns the last record of a given queryset.
        """
        queryset: QuerySet = self._clone()
        if kwargs:
            return await queryset.filter(**kwargs).order_by("-id").get()

        rows = await queryset.order_by("-id").all()
        if rows:
            return await self.embed_parent_in_result(rows[0])
        return None

    async def create(self, **kwargs: Any) -> EdgyModel:
        """
        Creates a record in a specific table.
        """
        queryset: QuerySet = self._clone()
        instance = queryset.model_class(**kwargs)
        instance.table = queryset.table
        instance = await instance.save(force_save=True)
        return await self.embed_parent_in_result(instance)

    async def bulk_create(self, objs: List[Dict]) -> None:
        """
        Bulk creates records in a table
        """
        queryset: QuerySet = self._clone()
        new_objs = [queryset._validate_kwargs(**obj) for obj in objs]

        expression = queryset.table.insert().values(new_objs)
        queryset._set_query_expression(expression)
        await queryset.database.execute_many(expression)

    async def bulk_update(self, objs: List[EdgyModel], fields: List[str]) -> None:
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
        for obj in objs:
            update = queryset.extract_column_values(
                obj.extract_db_fields(fields_plus_pk),
                queryset.model_class,
                is_update=True,
                is_partial=True,
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
        queryset._set_query_expression(expression)
        await queryset.database.execute_many(expression, update_list)

    async def delete(self) -> None:
        queryset: QuerySet = self._clone()

        await self.model_class.meta.signals.pre_delete.send_async(self.__class__, instance=self)

        expression = queryset.table.delete()
        for filter_clause in queryset.filter_clauses:
            expression = expression.where(filter_clause)

        queryset._set_query_expression(expression)
        await queryset.database.execute(expression)

        await self.model_class.meta.signals.post_delete.send_async(self.__class__, instance=self)

    async def update(self, **kwargs: Any) -> None:
        """
        Updates a record in a specific table with the given kwargs.
        """
        queryset: QuerySet = self._clone()

        kwargs = queryset.extract_column_values(kwargs, model_class=queryset.model_class)

        # Broadcast the initial update details
        await self.model_class.meta.signals.pre_update.send_async(
            self.__class__, instance=self, kwargs=kwargs
        )

        expression = queryset.table.update().values(**kwargs)

        for filter_clause in queryset.filter_clauses:
            expression = expression.where(filter_clause)

        queryset._set_query_expression(expression)
        await queryset.database.execute(expression)

        # Broadcast the update executed
        await self.model_class.meta.signals.post_update.send_async(self.__class__, instance=self)

    async def get_or_create(
        self, defaults: Dict[str, Any], **kwargs: Any
    ) -> Tuple[EdgyModel, bool]:
        """
        Creates a record in a specific table or updates if already exists.
        """
        queryset: QuerySet = self._clone()

        try:
            instance = await queryset.get(**kwargs)
            return instance, False
        except ObjectNotFound:
            kwargs.update(defaults)
            instance = await queryset.create(**kwargs)
            return instance, True

    async def update_or_create(
        self, defaults: Dict[str, Any], **kwargs: Any
    ) -> Tuple[EdgyModel, bool]:
        """
        Updates a record in a specific table or creates a new one.
        """
        queryset: QuerySet = self._clone()
        try:
            instance = await queryset.get(**kwargs)
            await instance.update(**defaults)
            return instance, False
        except ObjectNotFound:
            kwargs.update(defaults)
            instance = await queryset.create(**kwargs)
            return instance, True

    async def contains(self, instance: EdgyModel) -> bool:
        """Returns true if the QuerySet contains the provided object.
        False if otherwise.
        """
        queryset: QuerySet = self._clone()

        if getattr(instance, "pk", None) is None:
            raise ValueError("'obj' must be a model or reflect model instance.")
        # TODO: handle embed parent
        return await queryset.filter(pk=instance.pk).exists()

    async def _execute_iterate(
        self, fetch_all_at_once: bool = False
    ) -> AsyncIterator[Awaitable[EdgyModel]]:
        """
        Executes the query, iterate.
        """
        queryset: QuerySet = self._clone()
        if queryset.embed_parent:
            # activates distinct, not distinct on
            queryset.distinct_on = []

        expression = queryset._build_select()
        queryset._set_query_expression(expression)

        # Attach the raw query to the object
        queryset.model_class.raw_query = queryset.sql

        is_only_fields = bool(queryset._only)
        is_defer_fields = bool(queryset._defer)

        if not fetch_all_at_once and queryset.database.force_rollback:
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

        if fetch_all_at_once:
            for row in await queryset.database.fetch_all(expression):
                yield self.embed_parent_in_result(
                    queryset.model_class.from_sqla_row(
                        row,
                        select_related=queryset._select_related,
                        prefetch_related=queryset._prefetch_related,
                        is_only_fields=is_only_fields,
                        only_fields=queryset._only,
                        is_defer_fields=is_defer_fields,
                        exclude_secrets=queryset._exclude_secrets,
                        using_schema=queryset.using_schema,
                    )
                )
        else:
            async for row in queryset.database.iterate(expression):
                yield self.embed_parent_in_result(
                    queryset.model_class.from_sqla_row(
                        row,
                        select_related=queryset._select_related,
                        prefetch_related=queryset._prefetch_related,
                        is_only_fields=is_only_fields,
                        only_fields=queryset._only,
                        is_defer_fields=is_defer_fields,
                        exclude_secrets=queryset._exclude_secrets,
                        using_schema=queryset.using_schema,
                    )
                )

    async def _execute_all(self) -> List[EdgyModel]:
        return await asyncio.gather(
            *[coro async for coro in self._execute_iterate(fetch_all_at_once=True)]
        )

    def __await__(
        self,
    ) -> Generator[Any, None, List[EdgyModel]]:
        return self._execute_all().__await__()

    async def __aiter__(self) -> AsyncIterator[EdgyModel]:
        async for value in self._execute_iterate():
            yield await value

    def __class_getitem__(cls, *args: Any, **kwargs: Any) -> Any:
        return cls
