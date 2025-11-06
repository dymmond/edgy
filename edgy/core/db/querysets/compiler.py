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

    Args:
        table: The SQLAlchemy table or alias object.
    """
    try:
        return table.key  # type: ignore
    except AttributeError:
        # alias
        return table.name


class QueryCompiler:
    """
    Builds a SQLAlchemy query expression from a QuerySet's state.

    This class is instantiated by the QueryExecutor and is responsible
    for all SQL generation logic, including joins, columns, filtering,
    and ordering.
    """

    def __init__(self, queryset: BaseQuerySet) -> None:
        """
        Initializes the compiler with the state of a queryset.

        Args:
            queryset: The BaseQuerySet instance to compile.
        """
        self.queryset = queryset
        self.model_class = queryset.model_class
        self.database = queryset.database
        self.active_schema = queryset.active_schema

    def join_graph_data(self) -> tuple[Any, tables_and_models_type]:
        """
        Builds and caches the table relationships (joins) and the
        table-to-model mapping needed for this query.

        This replaces the mutation of `self.queryset._cached_select_related_expression`
        and encapsulates the join-building logic entirely within the compiler.

        Returns:
            A tuple containing:
                - The SQLAlchemy join expression.
                - The dictionary mapping prefixes to (table, model) tuples.
        """
        return self.build_join_graph()

    async def build_select(
        self,
    ) -> tuple[Any, tables_and_models_type]:
        """
        Builds the complete SQLAlchemy SELECT expression.

        This is the main public method of the compiler. It orchestrates
        the assembly of joins, columns, and all query clauses.

        Returns:
            A tuple containing:
                - The final, compiled SQLAlchemy SELECT expression.
                - The dictionary mapping prefixes to (table, model) tuples.
        """
        self.queryset._validate_only_and_defer()

        # Use the encapsulated cached_property
        joins, tables_and_models = self.queryset._get_join_graph_data()

        columns = self._build_columns(tables_and_models)

        # Build the query step-by-step
        expression = sqlalchemy.sql.select(*columns).set_label_style(sqlalchemy.LABEL_STYLE_NONE)
        expression = expression.select_from(joins)
        expression = await self._apply_where(expression, tables_and_models)
        expression = self._apply_ordering(expression, tables_and_models)
        expression = self._apply_grouping(expression, tables_and_models)
        expression = self._apply_limit_offset(expression)
        expression = self._apply_distinct(expression, tables_and_models)
        expression = self._apply_for_update(expression, tables_and_models)

        return expression, tables_and_models

    def _should_include_column(
        self,
        field_name: str,
        model_class: type[BaseModelType],
        prefix: str = "",
    ) -> bool:
        """
        Helper method to check if a column should be included based on
        .only(), .defer(), and .exclude_secrets() rules.

        Args:
            field_name: The name of the model field.
            model_class: The model class that owns the field.
            prefix: The join prefix (e.g., "related_model").

        Returns:
            True if the column should be included, False otherwise.
        """
        qs = self.queryset

        # Check .only() rules
        if qs._only:
            if not prefix and field_name not in qs._only:
                return False
            if prefix and prefix not in qs._only and f"{prefix}__{field_name}" not in qs._only:
                return False

        # Check .defer() rules
        if qs._defer:
            if not prefix and field_name in qs._defer:
                return False
            if prefix and (prefix in qs._defer or f"{prefix}__{field_name}" in qs._defer):
                return False

        # Check .exclude_secrets() rules
        if (  # noqa
            qs._exclude_secrets
            and field_name in model_class.meta.fields
            and model_class.meta.fields[field_name].secret
        ):
            return False

        # If no rules excluded it, include it
        return True

    def _build_columns(self, tables_and_models: tables_and_models_type) -> list[Any]:
        """
        Builds the list of columns for the SELECT statement.

        This method iterates over all tables in the join graph and uses
        the `_should_include_column` helper to decide which columns
        to add to the select list.

        Args:
            tables_and_models: The table/model mapping from `join_graph_data`.

        Returns:
            A list of SQLAlchemy Column objects and labeled columns.
        """
        columns_and_extra: list[Any] = [*self.queryset._extra_select]

        for prefix, (table, model_class) in tables_and_models.items():
            for column_key, column in table.columns.items():
                field_name = model_class.meta.columns_to_field.get(column_key, column_key)

                # Delegate the complex logic to the helper
                if not self._should_include_column(field_name, model_class, prefix):
                    continue

                # Add the column, aliasing if it's from a joined table
                if not prefix:
                    columns_and_extra.append(column)
                else:
                    columns_and_extra.append(column.label(f"{table.name}_{column_key}"))

        assert columns_and_extra, "no columns or extra_select specified"
        return columns_and_extra

    async def _apply_where(
        self, expression: Any, tables_and_models: tables_and_models_type
    ) -> Any:
        """Applies the WHERE clause to the select expression."""
        where_clause = await self.build_where_clause(tables_and_models)
        # where_clause can be None or an empty list, .where() handles this
        return expression.where(where_clause)

    def _apply_ordering(self, expression: Any, tables_and_models: tables_and_models_type) -> Any:
        """Applies the ORDER BY clause to the select expression."""
        if self.queryset._order_by:
            expression = expression.order_by(
                *self.queryset._build_order_by_iterable(self.queryset._order_by, tables_and_models)
            )
        return expression

    def _apply_grouping(self, expression: Any, tables_and_models: tables_and_models_type) -> Any:
        """Applies the GROUP BY clause to the select expression."""
        if self.queryset._group_by:
            expression = expression.group_by(
                *self.queryset._build_order_by_iterable(self.queryset._group_by, tables_and_models)
            )
        return expression

    def _apply_limit_offset(self, expression: Any) -> Any:
        """Applies the LIMIT and OFFSET clauses to the select expression."""
        if self.queryset.limit_count:
            expression = expression.limit(self.queryset.limit_count)
        if self.queryset._offset:
            expression = expression.offset(self.queryset._offset)
        return expression

    def _apply_distinct(self, expression: Any, tables_and_models: tables_and_models_type) -> Any:
        """Applies the DISTINCT or DISTINCT ON clause to the select expression."""
        if self.queryset.distinct_on is not None:
            expression = self._build_select_distinct(
                self.queryset.distinct_on,
                expression=expression,
                tables_and_models=tables_and_models,
            )
        return expression

    def _apply_for_update(self, expression: Any, tables_and_models: tables_and_models_type) -> Any:
        """Applies the SELECT...FOR UPDATE clause to the select expression."""
        if self.queryset._for_update:
            params = dict(self.queryset._for_update)

            # Map model classes in 'of' to their actual aliased tables
            if "of" in params and params["of"]:
                target_models = set(params["of"])
                of_tables: list[Any] = []
                for _, (table, model) in tables_and_models.items():
                    if model in target_models:
                        of_tables.append(table)

                if of_tables:
                    params["of"] = tuple(of_tables)
                else:
                    # No matching tables found in the query, remove 'of'
                    params.pop("of", None)
            expression = expression.with_for_update(**params)
        return expression

    async def build_where_clause(
        self, tables_and_models: tables_and_models_type | None = None, joins: Any | None = None
    ) -> Any:
        """
        Builds a SQLAlchemy WHERE clause from the queryset's filter and OR clauses.
        (Moved from BaseQuerySet)

        Args:
            tables_and_models: The table/model mapping. If None, it will be
                generated from the internal join graph.

        Returns:
            The SQLAlchemy WHERE clause (e.g., a BinaryExpression or None).
        """
        if tables_and_models is None:
            joins, tables_and_models = self.queryset._get_join_graph_data()

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

        # If there are no joins, we can return a simple AND clause
        if joins is None or len(tables_and_models) == 1:
            return clauses_mod.and_sqlalchemy(*where_clauses)

        # If there are joins, we must build a subquery to filter on the
        # main table's PKs to avoid row duplication issues.
        main_table, main_model = tables_and_models[""]
        pk_columns = [getattr(main_table.c, col) for col in main_model.pkcolumns]

        idtuple = sqlalchemy.tuple_(*pk_columns)

        # This subquery selects the PKs of the main table
        # after applying all joins and filters.
        expression = sqlalchemy.sql.select(*pk_columns).set_label_style(
            sqlalchemy.LABEL_STYLE_NONE
        )
        expression = expression.select_from(joins)

        # The final WHERE clause is `(pk1, pk2) IN (SELECT pk1, pk2 FROM ... WHERE ...)`
        return idtuple.in_(
            expression.where(
                *where_clauses,
            )
        )

    def build_join_graph(
        self,
    ) -> tuple[Any, tables_and_models_type]:
        """
        Builds the table relationships and joins for `select_related` operations.
        (Moved from BaseQuerySet)

        This is the core "magic" of select_related. It walks the relationship
        paths (e.g., "user__profile") and builds a graph of SQLAlchemy
        JOINs, aliasing tables as needed to handle complex or recursive
        relationships.

        This method no longer checks or mutates the queryset's cache.
        It is called by the `join_graph_data` cached_property.

        Returns:
            A tuple containing:
                - The root SQLAlchemy join expression.
                - The dictionary mapping prefixes to (table, model) tuples.

        Raises:
            QuerySetError: If a field in a path is invalid or not a relationship.
        """
        maintable = self.queryset.table
        select_from = maintable
        tables_and_models: tables_and_models_type = {"": (select_from, self.model_class)}
        _select_tables_and_models: tables_and_models_type = {"": (select_from, self.model_class)}
        transitions: dict[tuple[str, str, str], tuple[Any, tuple[str, str, str] | None, str]] = {}

        for select_path in self.queryset._select_related.union(self.queryset._select_related_weak):
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

        # Recursively build the JOINs from the transition graph
        while transitions:
            select_from = self._join_table_helper(
                select_from,
                next(iter(transitions.keys())),
                transitions=transitions,
                tables_and_models=_select_tables_and_models,
            )

        # Return the result directly
        return select_from, tables_and_models

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
        (Moved from BaseQuerySet)

        Args:
            join_clause: The current join clause to which new joins are added.
            current_transition: The key for the current transition.
            transitions: The dictionary of remaining transitions.
            tables_and_models: Mapping of prefixes to table/model objects.

        Returns:
            The updated join clause.
        """
        if current_transition not in transitions:
            return join_clause
        transition_value = transitions.pop(current_transition)

        # Build parent joins first
        if transition_value[1] is not None:
            join_clause = cls._join_table_helper(
                join_clause,
                transition_value[1],
                transitions=transitions,
                tables_and_models=tables_and_models,
            )

        # Build the current join
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
        Generates SQLAlchemy join conditions for a foreign key relationship.
        (Moved from BaseQuerySet)

        Args:
            foreign_key: The foreign key field defining the relationship.
            table: The SQLAlchemy table for the related model.
            reverse: True if the relationship is being traversed in reverse.
            former_table: The SQLAlchemy table for the source model.

        Yields:
            SQLAlchemy binary expressions for the join condition (e.g., `table.c.fk_id == former_table.c.id`).
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
        """
        Applies a DISTINCT or DISTINCT ON clause to the expression.
        (Moved from BaseQuerySet)

        Args:
            distinct_on: A list of field names for DISTINCT ON, or an empty
                list for a simple DISTINCT, or None to do nothing.
            expression: The SELECT expression to modify.
            tables_and_models: The table/model mapping.

        Returns:
            The modified SELECT expression.
        """
        if distinct_on:
            return expression.distinct(
                *(
                    self._prepare_distinct(distinct_el, tables_and_models)
                    for distinct_el in distinct_on
                )
            )
        else:
            # An empty list ([]) means simple DISTINCT
            return expression.distinct()

    def _prepare_distinct(
        self, distinct_on: str, tables_and_models: tables_and_models_type
    ) -> sqlalchemy.Column:
        """
        Finds the correct aliased SQLAlchemy column for a DISTINCT ON field name.
        (Moved from BaseQuerySet)

        Args:
            distinct_on: The field path (e.g., "name" or "related__name").
            tables_and_models: The table/model mapping.

        Returns:
            The corresponding SQLAlchemy Column object.
        """
        crawl_result = clauses_mod.clean_path_to_crawl_result(
            self.model_class,
            path=distinct_on,
            embed_parent=self.queryset.embed_parent_filters,
            model_database=self.database,
        )
        return tables_and_models[crawl_result.forward_path][0].columns[crawl_result.field_name]
