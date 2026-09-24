from __future__ import annotations

from collections.abc import Sequence
from typing import Any, cast

import sqlalchemy

from edgy.core.db.models.types import BaseModelType
from edgy.core.db.querysets import clauses as clauses_mod
from edgy.core.db.querysets.queryset import QuerySet
from edgy.exceptions import QuerySetError


class CombinedQuerySet(QuerySet):
    """
    A queryset that represents a SQL set operation between two querysets
    (UNION / UNION ALL / INTERSECT / EXCEPT).

    It inherits all public APIs from `QuerySet`. The internal compilation is
    overridden so that the outer SELECT is built on top of the set-operation
    subquery, allowing chaining (filter/order_by/distinct/limit/offset) to apply
    to the combined results.
    """

    def __init__(
        self,
        left: QuerySet,
        right: QuerySet,
        *,
        op: str = "union",
    ) -> None:
        # initialize as a normal QuerySet bound to the same model/database
        super().__init__(model_class=left.model_class)
        self.database = left.database
        # can't do this here
        self._injected_create_handler = None
        self._suppress_pk_deduplication = True
        self._left = left
        self._right = right
        self._op: str = op

        # update attrs used for caching
        self._cache.attrs = self.pkcolumns

        # carry over schema from the left side
        self.using_schema = left.using_schema
        self.active_schema = self.get_schema()

        # safety & consistency checks
        if left.model_class is not right.model_class:
            raise QuerySetError(
                detail="CombinedQuerySet requires both sides to have the same model class."
            )

        # for future if we allow left.model_class is not right.model_class:
        # if set(self._left.pkcolumns) != set(self._right.pkcolumns):
        #     raise QuerySetError(
        #         detail="CombinedQuerySet requires both sides to have the same pkcolumns."
        #     )

        if getattr(left.database, "dsn", None) != getattr(right.database, "dsn", None):  # noqa
            if getattr(left.database, "url", None) != getattr(right.database, "url", None):
                raise QuerySetError(
                    detail="Both querysets must be on the same database connection."
                )

    def _build_select_distinct(
        self,
        distinct_on: Sequence[str] | None,
        expression: Any,
        tables_and_models: dict[str, tuple[Any, type[BaseModelType]]],
    ) -> Any:
        """
        (Copied from QueryCompiler)
        Filters selects only specific fields. Leave empty to use simple distinct
        """
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

    def _prepare_distinct(
        self, distinct_on: str, tables_and_models: dict[str, tuple[Any, type[BaseModelType]]]
    ) -> sqlalchemy.Column:
        """
        (Copied from QueryCompiler and adapted for self)
        Prepares a field for use in a distinct-on clause.
        """
        crawl_result = clauses_mod.clean_path_to_crawl_result(
            self.model_class,
            path=distinct_on,
            embed_parent=self._embed_parent_filters,
            model_database=self.database,
        )
        # The subquery is aliased as "edgy_combined", which is in tables_and_models[""]
        return cast(
            sqlalchemy.Column,
            tables_and_models[crawl_result.forward_path][0].columns[crawl_result.field_name],
        )

    def _create_clone_instance(self) -> CombinedQuerySet:
        """
        Return a copy of this CombinedQuerySet that preserves the left/right branches,
        the chosen set operation, and all the usual queryset flags (filters, order_by, etc).
        """
        # Rebuild with the same branches/op
        queryset = type(self)(left=self._left, right=self._right, op=self._op)
        # Locking is not supported for combined sets; ensure none is carried
        queryset._for_update = None

        # Result caches are intentionally *not* copied; the clone should start "fresh".
        queryset._clear_cache(keep_result_cache=False, keep_cached_selected=False)
        return queryset

    async def _as_select_with_tables(
        self,
    ) -> tuple[Any, dict[str, tuple[Any, type[BaseModelType]]]]:
        """
        Build a SELECT over a set operation subquery.

        We compile left/right to SELECTs, perform the set op, then SELECT * FROM ( .. )
        so that subsequent clauses (filter/order_by/group_by/distinct/limit/offset)
        from this CombinedQuerySet apply to the merged rows.
        """
        # compile both branches
        left_sel, _ = await self._left.as_select_with_tables()
        right_sel, _ = await self._right.as_select_with_tables()

        # Ensure both sides project the same number of columns
        left_cols = list(left_sel.selected_columns)
        right_cols = list(right_sel.selected_columns)
        if len(left_cols) != len(right_cols):
            raise QuerySetError(
                detail=(
                    "UNION/INTERSECT/EXCEPT require both querysets to select the same columns. "
                    "Align projections (use only()/defer()/extra_select()) on both sides."
                )
            )

        # perform the set operation
        op = self._op
        if op == "union":
            set_expr = left_sel.union(right_sel)
        elif op == "union_all":
            set_expr = left_sel.union_all(right_sel)
        elif op in ("intersect", "intersect_all"):
            # SQLAlchemy Core lacks direct intersect_all(), but some dialects accept the SQL.
            # Use .intersect() and let DISTINCT semantics apply callers who need ALL should rely
            # on SQL dialect support or raw extra_select.
            set_expr = left_sel.intersect(right_sel)
        elif op in ("except", "except_all"):
            # Same note as above for ALL variants.
            set_expr = left_sel.except_(right_sel)
        else:
            raise QuerySetError(detail=f"Unsupported set operation: {self._op}")

        # Wrap into a subquery to apply outer clauses
        sub = set_expr.subquery("edgy_combined")

        # Outer SELECT re-projects all columns from the subquery.
        outer_cols = [getattr(sub.c, c.key) for c in left_cols]
        expression = (
            sqlalchemy.select(*outer_cols)
            .set_label_style(sqlalchemy.LABEL_STYLE_NONE)
            .select_from(sub)
        )

        # Minimal tables_and_models: map "" to the subquery and original model
        tables_and_models: dict[str, tuple[Any, type[BaseModelType]]] = {
            "": (sub, self.model_class)
        }

        # WHERE based on this CombinedQuerySet's filters (if any)
        where_clause = await self.build_where_clause(self, tables_and_models)
        if where_clause is not None:
            expression = expression.where(where_clause)

        # ORDER BY
        if self._order_by:
            expression = expression.order_by(
                *self._build_order_by_iterable(self._order_by, tables_and_models)
            )

        # GROUP BY
        if self._group_by:
            expression = expression.group_by(
                *self._build_order_by_iterable(self._group_by, tables_and_models)
            )

        # LIMIT / OFFSET
        if self.limit_count:
            expression = expression.limit(self.limit_count)
        if self._offset:
            expression = expression.offset(self._offset)

        # DISTINCT / DISTINCT ON
        if self.distinct_on is not None:
            expression = self._build_select_distinct(
                self.distinct_on, expression=expression, tables_and_models=tables_and_models
            )

        # Row locking on combined sets generally isn't supported in SQLAlchemy;
        # we explicitly ignore/forbid it to avoid dialect errors.
        if getattr(self, "_for_update", None):
            raise QuerySetError(
                detail="select_for_update() is not supported on combined querysets."
            )

        return expression, tables_and_models

    # factory helpers to construct CombinedQuerySet from a base QuerySet
    @classmethod
    def build(cls, left: QuerySet, right: QuerySet, *, op: str) -> CombinedQuerySet:
        return cls(left=left, right=right, op=op)
