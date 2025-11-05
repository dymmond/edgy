from __future__ import annotations

from typing import Any

import sqlalchemy

from edgy.core.db.models.types import BaseModelType
from edgy.core.db.querysets.base import QuerySet
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
        super().__init__(model_class=left.model_class, database=left.database)

        self._left = left
        self._right = right
        self._op: str = op

        # carry over schema from the left side
        self.using_schema = left.using_schema
        self.active_schema = self.get_schema()

        # safety & consistency checks
        if left.model_class is not right.model_class:
            raise QuerySetError(
                detail="CombinedQuerySet requires both sides to have the same model class."
            )
        if getattr(left.database, "dsn", None) != getattr(right.database, "dsn", None):  # noqa
            if getattr(left.database, "url", None) != getattr(right.database, "url", None):
                raise QuerySetError(
                    detail="Both querysets must be on the same database connection."
                )

    def _clone(self) -> CombinedQuerySet:
        """
        Return a copy of this CombinedQuerySet that preserves the left/right branches,
        the chosen set operation, and all the usual queryset flags (filters, order_by, etc).
        """
        # Rebuild with the same branches/op
        queryset = self.__class__(left=self._left, right=self._right, op=self._op)

        # Copy commonly-cloned attributes from BaseQuerySet._clone()
        queryset.filter_clauses = list(self.filter_clauses)
        queryset.or_clauses.extend(self.or_clauses)

        queryset._aliases = dict(getattr(self, "_aliases", {}))
        queryset.limit_count = self.limit_count
        queryset._offset = self._offset
        queryset._batch_size = self._batch_size
        queryset._order_by = self._order_by
        queryset._group_by = self._group_by

        # distinct handling mirrors BaseQuerySet._clone behavior
        queryset.distinct_on = (
            self.distinct_on[:] if isinstance(self.distinct_on, list) else self.distinct_on
        )

        queryset._only = set(self._only)
        queryset._defer = set(self._defer)

        queryset.embed_parent = self.embed_parent
        queryset.embed_parent_filters = self.embed_parent_filters
        queryset.using_schema = self.using_schema
        queryset.active_schema = self.active_schema

        queryset._extra_select = list(self._extra_select)
        queryset._reference_select = (
            self._reference_select.copy() if isinstance(self._reference_select, dict) else {}
        )

        # Select-related caches: copy values to avoid recomputation unless necessary
        queryset._select_related.update(self._select_related)
        queryset._select_related_weak.update(self._select_related_weak)
        queryset._cached_select_related_expression = self._cached_select_related_expression

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
