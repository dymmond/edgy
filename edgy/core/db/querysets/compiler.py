from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

import sqlalchemy

from edgy.core.db.fields.base import BaseForeignKey, RelationshipField
from edgy.core.utils.db import hash_tablekey
from edgy.exceptions import QuerySetError

from . import clauses as clauses_mod
from .types import tables_and_models_type

if TYPE_CHECKING:  # pragma: no cover
    from edgy.core.db.models.types import BaseModelType
    from edgy.core.db.querysets.base import BaseQuerySet


def get_table_key_or_name(table: sqlalchemy.Table | sqlalchemy.Alias) -> str:
    """
    Retrieves the key or name of a SQLAlchemy table or alias.
    """
    try:
        return table.key  # type: ignore
    except AttributeError:
        # alias
        return table.name


class QueryCompiler:
    """
    Builds a SQLAlchemy query expression from a QuerySet's state.
    """

    def __init__(self, queryset: BaseQuerySet | Any) -> None:
        self.queryset = queryset
        self.model_class = queryset.model_class
        self.database = queryset.database
        self.active_schema = queryset.active_schema

    async def build_select(
        self,
    ) -> tuple[Any, tables_and_models_type]:
        """
        This is the refactored _as_select_with_tables.
        It builds the complete SQLAlchemy SELECT expression.
        """
        self.queryset._validate_only_and_defer()
        joins, tables_and_models = self._build_tables_join_from_relationship()

        columns = self._build_columns(tables_and_models)

        expression = sqlalchemy.sql.select(*columns).set_label_style(sqlalchemy.LABEL_STYLE_NONE)
        expression = expression.select_from(joins)
        expression = await self._apply_where(expression, tables_and_models)
        expression = self._apply_ordering(expression, tables_and_models)
        expression = self._apply_grouping(expression, tables_and_models)
        expression = self._apply_limit_offset(expression)
        expression = self._apply_distinct(expression, tables_and_models)
        expression = self._apply_for_update(expression, tables_and_models)

        return expression, tables_and_models

    def _build_columns(self, tables_and_models: tables_and_models_type) -> list[Any]:
        """
        Builds the list of columns for the SELECT statement,
        honoring .only(), .defer(), and .exclude_secrets().
        """
        qs = self.queryset
        columns_and_extra: list[Any] = [*qs._extra_select]

        for prefix, (table, model_class) in tables_and_models.items():
            if not prefix:
                for column_key, column in table.columns.items():
                    field_name = model_class.meta.columns_to_field.get(column_key, column_key)
                    if qs._only and field_name not in qs._only:
                        continue
                    if qs._defer and field_name in qs._defer:
                        continue
                    if (
                        qs._exclude_secrets
                        and field_name in model_class.meta.fields
                        and model_class.meta.fields[field_name].secret
                    ):
                        continue
                    columns_and_extra.append(column)
            else:
                for column_key, column in table.columns.items():
                    field_name = model_class.meta.columns_to_field.get(column_key, column_key)
                    if (
                        qs._only
                        and prefix not in qs._only
                        and f"{prefix}__{field_name}" not in qs._only
                    ):
                        continue
                    if qs._defer and (
                        prefix in qs._defer or f"{prefix}__{field_name}" in qs._defer
                    ):
                        continue
                    if (
                        qs._exclude_secrets
                        and field_name in model_class.meta.fields
                        and model_class.meta.fields[field_name].secret
                    ):
                        continue
                    columns_and_extra.append(column.label(f"{table.name}_{column_key}"))

        assert columns_and_extra, "no columns or extra_select specified"
        return columns_and_extra

    async def _apply_where(
        self, expression: Any, tables_and_models: tables_and_models_type
    ) -> Any:
        where_clause = await self.build_where_clause(tables_and_models)
        return expression.where(where_clause)

    def _apply_ordering(self, expression: Any, tables_and_models: tables_and_models_type) -> Any:
        if self.queryset._order_by:
            expression = expression.order_by(
                *self.queryset._build_order_by_iterable(self.queryset._order_by, tables_and_models)
            )
        return expression

    def _apply_grouping(self, expression: Any, tables_and_models: tables_and_models_type) -> Any:
        if self.queryset._group_by:
            expression = expression.group_by(
                *self.queryset._build_order_by_iterable(self.queryset._group_by, tables_and_models)
            )
        return expression

    def _apply_limit_offset(self, expression: Any) -> Any:
        if self.queryset.limit_count:
            expression = expression.limit(self.queryset.limit_count)
        if self.queryset._offset:
            expression = expression.offset(self.queryset._offset)
        return expression

    def _apply_distinct(self, expression: Any, tables_and_models: tables_and_models_type) -> Any:
        if self.queryset.distinct_on is not None:
            expression = self._build_select_distinct(
                self.queryset.distinct_on,
                expression=expression,
                tables_and_models=tables_and_models,
            )
        return expression

    def _apply_for_update(self, expression: Any, tables_and_models: tables_and_models_type) -> Any:
        if self.queryset._for_update:
            params = dict(self.queryset._for_update)
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
        return expression

    async def build_where_clause(
        self, tables_and_models: tables_and_models_type | None = None
    ) -> Any:
        """
        Builds a SQLAlchemy WHERE clause from the queryset's filter and OR clauses.
        (Moved from BaseQuerySet)
        """
        joins: Any | None = None
        if tables_and_models is None:
            joins, tables_and_models = self._build_tables_join_from_relationship()

        where_clauses: list[Any] = []
        if self.queryset.or_clauses:
            where_clauses.append(
                await clauses_mod.parse_clause_arg(
                    clauses_mod.or_(*self.queryset.or_clauses, no_select_related=True),
                    self.queryset,
                    tables_and_models,
                )
            )

        if self.queryset.filter_clauses:
            where_clauses.extend(
                await clauses_mod.parse_clause_args(
                    self.queryset.filter_clauses, self.queryset, tables_and_models
                )
            )

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

    def _build_tables_join_from_relationship(
        self,
    ) -> tuple[Any, tables_and_models_type]:
        """
        Builds the table relationships and joins for `select_related` operations.
        (Moved from BaseQuerySet)
        """
        if self.queryset._cached_select_related_expression is None:
            maintable = self.queryset.table
            select_from = maintable
            tables_and_models: tables_and_models_type = {"": (select_from, self.model_class)}
            _select_tables_and_models: tables_and_models_type = {
                "": (select_from, self.model_class)
            }
            transitions: dict[
                tuple[str, str, str], tuple[Any, tuple[str, str, str] | None, str]
            ] = {}

            for select_path in self.queryset._select_related.union(
                self.queryset._select_related_weak
            ):
                model_class = self.model_class
                former_table = maintable
                former_transition = None
                prefix: str = ""
                _select_prefix: str = ""
                injected_prefix: bool | str = False
                model_database: Any = self.database  # Using Any to avoid Database import

                while select_path:
                    field_name = select_path.split("__", 1)[0]
                    try:
                        field = model_class.meta.fields[field_name]
                    except KeyError:
                        raise QuerySetError(
                            detail=f'Selected field "{field_name}" does not exist on {model_class}.'
                        ) from None

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

                    model_database = None
                    if injected_prefix:
                        injected_prefix = False
                    else:
                        prefix = f"{prefix}__{field_name}" if prefix else f"{field_name}"

                    _select_prefix = (
                        f"{_select_prefix}__{field_name}" if _select_prefix else f"{field_name}"
                    )

                    if foreign_key.is_m2m and foreign_key.embed_through != "":
                        model_class = foreign_key.through
                        if foreign_key.embed_through is False:
                            injected_prefix = True
                        else:
                            injected_prefix = f"{prefix}__{foreign_key.embed_through}"
                        if reverse:
                            select_path = f"{foreign_key.from_foreign_key}__{select_path}"
                        else:
                            select_path = f"{foreign_key.to_foreign_key}__{select_path}"
                        select_path = select_path.removesuffix("__")
                        if reverse:
                            foreign_key = model_class.meta.fields[foreign_key.to_foreign_key]
                        else:
                            foreign_key = model_class.meta.fields[foreign_key.from_foreign_key]
                            reverse = True

                    if _select_prefix in _select_tables_and_models:
                        table: Any = _select_tables_and_models[_select_prefix][0]
                    else:
                        table = model_class.table_schema(self.active_schema)
                        table = table.alias(hash_tablekey(tablekey=table.key, prefix=prefix))

                    transition_key = (get_table_key_or_name(former_table), table.name, field_name)
                    if transition_key in transitions:
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
                        tables_and_models[injected_prefix] = table, model_class

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

            self.queryset._cached_select_related_expression = (
                select_from,
                tables_and_models,
            )
        return self.queryset._cached_select_related_expression

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
        Recursively builds SQLAlchemy join clauses.
        (Moved from BaseQuerySet)
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

    @staticmethod
    def _select_from_relationship_clause_generator(
        foreign_key: BaseForeignKey,
        table: Any,
        reverse: bool,
        former_table: Any,
    ) -> Any:
        """
        Generates SQLAlchemy WHERE clauses for joining tables.
        (Moved from BaseQuerySet)
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

    def _build_select_distinct(
        self,
        distinct_on: Sequence[str] | None,
        expression: Any,
        tables_and_models: tables_and_models_type,
    ) -> Any:
        """(Moved from BaseQuerySet)"""
        if distinct_on:
            return expression.distinct(
                *(
                    self._prepare_distinct(distinct_el, tables_and_models)
                    for distinct_el in distinct_on
                )
            )
        else:
            return expression.distinct()

    def _prepare_distinct(
        self, distinct_on: str, tables_and_models: tables_and_models_type
    ) -> sqlalchemy.Column:
        """(Moved from BaseQuerySet)"""
        crawl_result = clauses_mod.clean_path_to_crawl_result(
            self.model_class,
            path=distinct_on,
            embed_parent=self.queryset.embed_parent_filters,
            model_database=self.database,
        )
        return tables_and_models[crawl_result.forward_path][0].columns[crawl_result.field_name]
