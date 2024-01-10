import copy
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncIterator,
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
from edgy.core.db.fields._base_fk import BaseForeignKey
from edgy.core.db.fields.foreign_keys import BaseForeignKeyField
from edgy.core.db.fields.one_to_one_keys import BaseOneToOneKeyField
from edgy.core.db.querysets.mixins import EdgyModel, QuerySetPropsMixin, TenancyMixin
from edgy.core.db.querysets.prefetch import PrefetchMixin
from edgy.core.db.querysets.protocols import AwaitableQuery
from edgy.core.utils.models import DateParser, ModelParser
from edgy.exceptions import MultipleObjectsReturned, ObjectNotFound, QuerySetError
from edgy.protocols.queryset import QuerySetProtocol

if TYPE_CHECKING:  # pragma: no cover
    from edgy import Database
    from edgy.core.db.models import Model, ReflectModel


class BaseQuerySet(
    TenancyMixin,
    QuerySetPropsMixin,
    PrefetchMixin,
    DateParser,
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
        distinct_on: Any = None,
        only_fields: Any = None,
        defer_fields: Any = None,
        m2m_related: Any = None,
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
        self.distinct_on = [] if distinct_on is None else distinct_on
        self._only = [] if only_fields is None else only_fields
        self._defer = [] if defer_fields is None else defer_fields
        self._expression = None
        self._cache = None
        self._m2m_related = m2m_related  # type: ignore
        self.using_schema = using_schema
        self._exclude_secrets = exclude_secrets or False
        self.extra: Dict[str, Any] = {}

        # Making sure the queryset always starts without any schema associated unless specified
        if self.is_m2m and not self._m2m_related:
            self._m2m_related = self.model_class.meta.multi_related[0]

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
            clause = sqlalchemy.sql.and_(*filter_clauses)
        expression = expression.where(clause)
        return expression

    def _build_or_clauses_expression(self, or_clauses: Any, expression: Any) -> Any:
        """Builds the filter clauses expression"""
        if len(or_clauses) == 1:
            clause = or_clauses[0]
        else:
            clause = sqlalchemy.sql.or_(*or_clauses)
        expression = expression.where(clause)
        return expression

    def _build_select_distinct(self, distinct_on: Any, expression: Any) -> Any:
        """Filters selects only specific fields"""
        distinct_on = list(map(self._prepare_fields_for_distinct, distinct_on))
        expression = expression.distinct(*distinct_on)
        return expression

    def _is_multiple_foreign_key(
        self, model_class: Union[Type["Model"], Type["ReflectModel"]]
    ) -> Tuple[bool, List[Tuple[str, str, str]]]:
        """
        Checks if the table has multiple foreign keys to the same table.
        Iterates through all fields of type ForeignKey and OneToOneField and checks if there are
        multiple FKs to the same destination table.

        Returns a tuple of bool, list of tuples
        """
        fields = model_class.fields  # type: ignore
        foreign_keys = []
        has_many = False

        counter = 0

        for key, value in fields.items():
            tablename = None

            if counter > 1:
                has_many = True

            if isinstance(value, (BaseForeignKeyField, BaseOneToOneKeyField)):
                tablename = value.to if isinstance(value.to, str) else value.to.__name__  # type: ignore

                if tablename not in foreign_keys:
                    foreign_keys.append((key, tablename, value.related_name))
                    counter += 1
                else:
                    counter += 1

        return has_many, foreign_keys

    def _build_tables_select_from_relationship(self) -> Any:
        """
        Builds the tables relationships and joins.
        When a table contains more than one foreign key pointing to the same
        destination table, a lookup for the related field is made to understand
        from which foreign key the table is looked up from.
        """
        queryset: "QuerySet" = self._clone()

        tables = [queryset.table]
        select_from = queryset.table
        has_many_fk_same_table = False

        # Select related
        for item in queryset._select_related:
            # For m2m relationships
            model_class = queryset.model_class
            select_from = queryset.table

            for part in item.split("__"):
                try:
                    model_class = model_class.fields[part].target
                except KeyError:
                    # Check related fields
                    model_class = getattr(model_class, part).related_from
                    has_many_fk_same_table, keys = self._is_multiple_foreign_key(model_class)

                table = model_class.table

                # If there is multiple FKs to the same table
                if not has_many_fk_same_table:
                    select_from = sqlalchemy.sql.join(select_from, table)  # type: ignore
                else:
                    lookup_field = None

                    # Extract the table field from the related
                    # Assign to a lookup_field
                    for values in keys:
                        field, _, related_name = values
                        if related_name == part:
                            lookup_field = field
                            break

                    select_from = sqlalchemy.sql.join(  # type: ignore
                        select_from,
                        table,
                        select_from.c.id == getattr(table.c, lookup_field),
                    )

                tables.append(table)

        return tables, select_from

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

        for name, field in model_class.fields.items():
            if isinstance(field, BaseForeignKey):
                # Making sure the foreign key is always added unless is a secret
                if not field.secret:
                    columns.append(name)
                    columns.extend(
                        self._secret_recursive_names(model_class=field.target, columns=columns)
                    )
                continue
            if not field.secret:
                columns.append(name)

        columns = list(set(columns))
        return columns

    def _build_select(self) -> Any:
        """
        Builds the query select based on the given parameters and filters.
        """
        queryset: "QuerySet" = self._clone()

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

        if queryset.distinct_on:
            expression = queryset._build_select_distinct(
                queryset.distinct_on, expression=expression
            )

        queryset._expression = expression  # type: ignore
        return expression

    def _filter_query(
        self,
        exclude: bool = False,
        or_: bool = False,
        **kwargs: Any,
    ) -> "QuerySet":
        from edgy.core.db.models import Model

        clauses = []
        filter_clauses = self.filter_clauses
        or_clauses = self.or_clauses
        select_related = list(self._select_related)
        prefetch_related = list(self._prefetch_related)

        # Making sure for queries we use the main class and not the proxy
        # And enable the parent
        if self.model_class.is_proxy_model:
            self.model_class = self.model_class.parent

        if kwargs.get("pk"):
            pk_name = self.model_class.pkname
            kwargs[pk_name] = kwargs.pop("pk")

        for key, value in kwargs.items():
            if "__" in key:
                parts = key.split("__")

                # Determine if we should treat the final part as a
                # filter operator or as a related field.
                if parts[-1] in settings.filter_operators:
                    op = parts[-1]
                    field_name = parts[-2]
                    related_parts = parts[:-2]
                else:
                    op = "exact"
                    field_name = parts[-1]
                    related_parts = parts[:-1]

                model_class = self.model_class
                if related_parts:
                    # Add any implied select_related
                    related_str = "__".join(related_parts)
                    if related_str not in select_related:
                        select_related.append(related_str)

                    # Walk the relationships to the actual model class
                    # against which the comparison is being made.
                    for part in related_parts:
                        try:
                            model_class = model_class.fields[part].target
                        except KeyError:
                            model_class = getattr(model_class, part).related_from

                column = model_class.table.columns[field_name]

            else:
                op = "exact"
                try:
                    column = self.table.columns[key]
                except KeyError as error:
                    # Check for related fields
                    # if an Attribute error is raised, we need to make sure
                    # It raises the KeyError from the previous check
                    try:
                        model_class = getattr(self.model_class, key).related_to
                        column = model_class.table.columns[settings.default_related_lookup_field]
                    except AttributeError:
                        raise KeyError(str(error)) from error

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

            if isinstance(value, Model):
                value = value.pk

            clause = getattr(column, op_attr)(value)
            clause.modifiers["escape"] = "\\" if has_escaped_character else None
            clauses.append(clause)

        if exclude:
            if not or_:
                filter_clauses.append(sqlalchemy.not_(sqlalchemy.sql.and_(*clauses)))
            else:
                or_clauses.append(sqlalchemy.not_(sqlalchemy.sql.and_(*clauses)))
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
                m2m_related=self.m2m_related,
                table=self.table,
                exclude_secrets=self._exclude_secrets,
                using_schema=self.using_schema,
            ),
        )

    def _validate_kwargs(self, **kwargs: Any) -> Any:
        return self._extract_values_from_field(kwargs, model_class=self.model_class)

    def _prepare_order_by(self, order_by: str) -> Any:
        reverse = order_by.startswith("-")
        order_by = order_by.lstrip("-")
        order_col = self.table.columns[order_by]
        return order_col.desc() if reverse else order_col

    def _prepare_group_by(self, group_by: str) -> Any:
        group_by = group_by.lstrip("-")
        group_col = self.table.columns[group_by]
        return group_col

    def _prepare_fields_for_distinct(self, distinct_on: str) -> Any:
        _distinct_on: sqlalchemy.Column = self.table.columns[distinct_on]
        return _distinct_on

    def _clone(self) -> Any:
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
        queryset._m2m_related = copy.copy(self._m2m_related)
        queryset._only = copy.copy(self._only)
        queryset._defer = copy.copy(self._defer)
        queryset._database = self.database
        queryset.table = self.table
        queryset.extra = self.extra
        queryset._exclude_secrets = self._exclude_secrets
        queryset.using_schema = self.using_schema

        return queryset


class QuerySet(BaseQuerySet, QuerySetProtocol):
    """
    QuerySet object used for query retrieving.
    """

    def __get__(self, instance: Any, owner: Any) -> "QuerySet":
        return self.__class__(model_class=owner)

    @property
    def sql(self) -> str:
        return str(self._expression)

    @sql.setter
    def sql(self, value: Any) -> None:
        self._expression = value

    async def __aiter__(self) -> AsyncIterator[EdgyModel]:
        for value in await self:
            yield value

    def _set_query_expression(self, expression: Any) -> None:
        """
        Sets the value of the sql property to the expression used.
        """
        self.sql = expression
        self.model_class.raw_query = self.sql

    def _filter_or_exclude(
        self,
        clause: Optional[sqlalchemy.sql.expression.BinaryExpression] = None,
        exclude: bool = False,
        **kwargs: Any,
    ) -> "QuerySet":
        """
        Filters or excludes a given clause for a specific QuerySet.
        """
        queryset: "QuerySet" = self._clone()
        if clause is None:
            if not exclude:
                return queryset._filter_query(**kwargs)
            return queryset._filter_query(exclude=exclude, **kwargs)

        queryset.filter_clauses.append(clause)
        return queryset

    def filter(
        self,
        clause: Optional[sqlalchemy.sql.expression.BinaryExpression] = None,
        **kwargs: Any,
    ) -> "QuerySet":
        """
        Filters the QuerySet by the given kwargs and clause.
        """
        return self._filter_or_exclude(clause=clause, **kwargs)

    def or_(
        self,
        clause: Optional[sqlalchemy.sql.expression.BinaryExpression] = None,
        **kwargs: Any,
    ) -> "QuerySet":
        """
        Filters the QuerySet by the OR operand.
        """
        queryset: "QuerySet" = self._clone()
        queryset = self.filter(clause=clause, or_=True, **kwargs)
        return queryset

    def and_(
        self,
        clause: Optional[sqlalchemy.sql.expression.BinaryExpression] = None,
        **kwargs: Any,
    ) -> "QuerySet":
        """
        Filters the QuerySet by the AND operand.
        """
        queryset: "QuerySet" = self._clone()
        queryset = self.filter(clause=clause, **kwargs)
        return queryset

    def not_(
        self,
        clause: Optional[sqlalchemy.sql.expression.BinaryExpression] = None,
        **kwargs: Any,
    ) -> "QuerySet":
        """
        Filters the QuerySet by the NOT operand.
        """
        queryset: "QuerySet" = self._clone()
        queryset = queryset.exclude(clause=clause, **kwargs)
        return queryset

    def exclude(
        self,
        clause: Optional[sqlalchemy.sql.expression.BinaryExpression] = None,
        **kwargs: Any,
    ) -> "QuerySet":
        """
        Exactly the same as the filter but for the exclude.
        """
        queryset: "QuerySet" = self._clone()
        queryset = self._filter_or_exclude(clause=clause, exclude=True, **kwargs)
        return queryset

    def exclude_secrets(
        self,
        clause: Optional[sqlalchemy.sql.expression.BinaryExpression] = None,
        **kwargs: Any,
    ) -> "QuerySet":
        """
        Excludes any field that contains the `secret=True` declared from being leaked.
        """
        queryset: "QuerySet" = self._clone()
        queryset._exclude_secrets = True
        queryset = queryset.filter(clause=clause, **kwargs)
        return queryset

    def lookup(self, term: Any) -> "QuerySet":
        """
        Broader way of searching for a given term
        """
        queryset: "QuerySet" = self._clone()
        if not term:
            return queryset

        filter_clauses = list(queryset.filter_clauses)
        value = f"%{term}%"

        search_fields = [
            name
            for name, field in queryset.model_class.fields.items()
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
        queryset: "QuerySet" = self._clone()
        queryset._order_by = order_by
        return queryset

    def limit(self, limit_count: int) -> "QuerySet":
        """
        Returns a QuerySet limited by.
        """
        queryset: "QuerySet" = self._clone()
        queryset.limit_count = limit_count
        return queryset

    def offset(self, offset: int) -> "QuerySet":
        """
        Returns a Queryset limited by the offset.
        """
        queryset: "QuerySet" = self._clone()
        queryset._offset = offset
        return queryset

    def group_by(self, *group_by: Sequence[str]) -> "QuerySet":
        """
        Returns the values grouped by the given fields.
        """
        queryset: "QuerySet" = self._clone()
        queryset._group_by = group_by
        return queryset

    def distinct(self, *distinct_on: Sequence[str]) -> "QuerySet":
        """
        Returns a queryset with distinct results.
        """
        queryset: "QuerySet" = self._clone()
        queryset.distinct_on = distinct_on
        return queryset

    def only(self, *fields: Sequence[str]) -> "QuerySet":
        """
        Returns a list of models with the selected only fields and always the primary
        key.
        """
        only_fields = [sqlalchemy.text(field) for field in fields]
        if self.model_class.pkname not in fields:
            only_fields.insert(0, sqlalchemy.text(self.model_class.pkname))

        queryset: "QuerySet" = self._clone()
        queryset._only = only_fields
        return queryset

    def defer(self, *fields: Sequence[str]) -> "QuerySet":
        """
        Returns a list of models with the selected only fields and always the primary
        key.
        """
        queryset: "QuerySet" = self._clone()
        queryset._defer = fields
        return queryset

    def select_related(self, related: Any) -> "QuerySet":
        """
        Returns a QuerySet that will “follow” foreign-key relationships, selecting additional
        related-object data when it executes its query.

        This is a performance booster which results in a single more complex query but means

        later use of foreign-key relationships won’t require database queries.
        """
        queryset: "QuerySet" = self._clone()
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
        queryset: "QuerySet" = self._clone()
        rows: List[Type["Model"]] = await queryset.all()

        if not isinstance(fields, list):
            raise QuerySetError(detail="Fields must be an iterable.")

        if not fields:
            rows = [row.model_dump(exclude=exclude, exclude_none=exclude_none) for row in rows]  # type: ignore
        else:
            rows = [
                row.model_dump(exclude=exclude, exclude_none=exclude_none, include=fields)  # type: ignore
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
        queryset: "QuerySet" = self._clone()
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
        queryset: "QuerySet" = self._clone()
        expression = queryset._build_select()
        expression = sqlalchemy.exists(expression).select()
        queryset._set_query_expression(expression)
        _exists = await queryset.database.fetch_val(expression)
        return cast("bool", _exists)

    async def count(self, **kwargs: Any) -> int:
        """
        Returns an indicating the total records.
        """
        queryset: "QuerySet" = self._clone()
        expression = queryset._build_select().alias("subquery_for_count")
        expression = sqlalchemy.func.count().select().select_from(expression)
        queryset._set_query_expression(expression)
        _count = await queryset.database.fetch_val(expression)
        return cast("int", _count)

    async def get_or_none(self, **kwargs: Any) -> Union[EdgyModel, None]:
        """
        Fetch one object matching the parameters or returns None.
        """
        queryset: "QuerySet" = self.filter(**kwargs)
        expression = queryset._build_select().limit(2)
        queryset._set_query_expression(expression)
        rows = await queryset.database.fetch_all(expression)

        if not rows:
            return None
        if len(rows) > 1:
            raise MultipleObjectsReturned()
        return queryset.model_class.from_sqla_row(
            rows[0],
            select_related=queryset._select_related,
            exclude_secrets=queryset._exclude_secrets,
            using_schema=queryset.using_schema,
        )

    async def _all(self, **kwargs: Any) -> List[EdgyModel]:
        """
        Executes the query.
        """
        queryset: "QuerySet" = self._clone()
        if queryset.is_m2m:
            queryset.distinct_on = [queryset.m2m_related]

        if kwargs:
            return await queryset.filter(**kwargs).all()

        expression = queryset._build_select()
        queryset._set_query_expression(expression)

        rows = await queryset.database.fetch_all(expression)

        # Attach the raw query to the object
        queryset.model_class.raw_query = queryset.sql

        is_only_fields = True if queryset._only else False
        is_defer_fields = True if queryset._defer else False

        results = [
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
            for row in rows
        ]

        if not queryset.is_m2m:
            return results

        all_results = [getattr(result, queryset.m2m_related) for result in results]
        return all_results

    def all(self, **kwargs: Any) -> "QuerySet":
        """
        Returns the queryset records based on specific filters
        """
        queryset: "QuerySet" = self._clone()
        queryset.extra = kwargs
        return queryset

    async def get(self, **kwargs: Any) -> EdgyModel:
        """
        Returns a single record based on the given kwargs.
        """
        queryset: "QuerySet" = self._clone()

        if kwargs:
            return await queryset.filter(**kwargs).get()

        expression = queryset._build_select().limit(2)
        rows = await queryset.database.fetch_all(expression)
        queryset._set_query_expression(expression)

        is_only_fields = True if queryset._only else False
        is_defer_fields = True if queryset._defer else False

        if not rows:
            raise ObjectNotFound()
        if len(rows) > 1:
            raise MultipleObjectsReturned()

        return queryset.model_class.from_sqla_row(
            rows[0],
            select_related=queryset._select_related,
            is_only_fields=is_only_fields,
            only_fields=queryset._only,
            is_defer_fields=is_defer_fields,
            prefetch_related=queryset._prefetch_related,
            exclude_secrets=queryset._exclude_secrets,
            using_schema=queryset.using_schema,
        )

    async def first(self, **kwargs: Any) -> Union[EdgyModel, None]:
        """
        Returns the first record of a given queryset.
        """
        queryset: "QuerySet" = self._clone()
        if kwargs:
            return await queryset.filter(**kwargs).order_by("id").get()

        rows = await queryset.limit(1).order_by("id").all()
        if rows:
            return rows[0]
        return None

    async def last(self, **kwargs: Any) -> Union[EdgyModel, None]:
        """
        Returns the last record of a given queryset.
        """
        queryset: "QuerySet" = self._clone()
        if kwargs:
            return await queryset.filter(**kwargs).order_by("-id").get()

        rows = await queryset.order_by("-id").all()
        if rows:
            return rows[0]
        return None

    async def create(self, **kwargs: Any) -> EdgyModel:
        """
        Creates a record in a specific table.
        """
        queryset: "QuerySet" = self._clone()
        kwargs = queryset._validate_kwargs(**kwargs)
        instance = queryset.model_class(**kwargs)
        instance.table = queryset.table
        instance = await instance.save(force_save=True, values=kwargs)
        return instance

    async def bulk_create(self, objs: List[Dict]) -> None:
        """
        Bulk creates records in a table
        """
        queryset: "QuerySet" = self._clone()
        new_objs = [queryset._validate_kwargs(**obj) for obj in objs]

        expression = queryset.table.insert().values(new_objs)
        queryset._set_query_expression(expression)
        await queryset.database.execute(expression)

    async def bulk_update(self, objs: List[EdgyModel], fields: List[str]) -> None:
        """
        Bulk updates records in a table.

        A similar solution was suggested here: https://github.com/encode/orm/pull/148

        It is thought to be a clean approach to a simple problem so it was added here and
        refactored to be compatible with Edgy.
        """
        queryset: "QuerySet" = self._clone()

        new_objs = []
        for obj in objs:
            new_obj = {}
            for key, value in obj.__dict__.items():
                if key in fields:
                    new_obj[key] = self._resolve_value(value)
            new_objs.append(new_obj)

        new_objs = [
            queryset._extract_values_from_field(obj, queryset.model_class) for obj in new_objs
        ]

        pk = getattr(queryset.table.c, queryset.pkname)
        expression = queryset.table.update().where(pk == sqlalchemy.bindparam(queryset.pkname))
        kwargs: Dict[Any, Any] = {
            field: sqlalchemy.bindparam(field) for obj in new_objs for field in obj.keys()
        }
        pks = [{queryset.pkname: getattr(obj, queryset.pkname)} for obj in objs]

        query_list = []
        for pk, value in zip(pks, new_objs):  # noqa
            query_list.append({**pk, **value})

        expression = expression.values(kwargs)
        queryset._set_query_expression(expression)
        await queryset.database.execute_many(str(expression), query_list)

    async def delete(self) -> None:
        queryset: "QuerySet" = self._clone()

        await self.model_class.signals.pre_delete.send(sender=self.__class__, instance=self)

        expression = queryset.table.delete()
        for filter_clause in queryset.filter_clauses:
            expression = expression.where(filter_clause)

        queryset._set_query_expression(expression)
        await queryset.database.execute(expression)

        await self.model_class.signals.post_delete.send(sender=self.__class__, instance=self)

    async def update(self, **kwargs: Any) -> None:
        """
        Updates a record in a specific table with the given kwargs.
        """
        queryset: "QuerySet" = self._clone()

        extracted_fields = queryset._extract_values_from_field(
            kwargs, model_class=queryset.model_class
        )
        kwargs = queryset._update_auto_now_fields(extracted_fields, queryset.model_class.fields)

        # Broadcast the initial update details
        await self.model_class.signals.pre_update.send(
            sender=self.__class__, instance=self, kwargs=kwargs
        )

        expression = queryset.table.update().values(**kwargs)

        for filter_clause in queryset.filter_clauses:
            expression = expression.where(filter_clause)

        queryset._set_query_expression(expression)
        await queryset.database.execute(expression)

        # Broadcast the update executed
        await self.model_class.signals.post_update.send(sender=self.__class__, instance=self)

    async def get_or_create(
        self, defaults: Dict[str, Any], **kwargs: Any
    ) -> Tuple[EdgyModel, bool]:
        """
        Creates a record in a specific table or updates if already exists.
        """
        queryset: "QuerySet" = self._clone()

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
        queryset: "QuerySet" = self._clone()
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
        queryset: "QuerySet" = self._clone()

        if getattr(instance, "pk", None) is None:
            raise ValueError("'obj' must be a model or reflect model instance.")
        return await queryset.filter(pk=instance.pk).exists()

    async def _execute(self) -> Any:
        queryset: "QuerySet" = self._clone()
        records = await queryset._all(**queryset.extra)
        return records

    def __await__(
        self,
    ) -> Generator[Any, None, List[EdgyModel]]:
        return self._execute().__await__()

    def __class_getitem__(cls, *args: Any, **kwargs: Any) -> Any:
        return cls
