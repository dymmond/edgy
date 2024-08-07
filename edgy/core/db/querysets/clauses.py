from __future__ import annotations

from typing import TYPE_CHECKING, Any, Union

import sqlalchemy
from sqlalchemy import ColumnCollection

if TYPE_CHECKING:
    from edgy.core.db.models import Model


class _EnhancedClausesHelper:
    def __init__(self, op: Any, default_empty: Any) -> None:
        self.op = op
        self.default_empty = default_empty

    def __call__(self, *args: Any) -> Any:
        if len(args) == 0:
            args = (self.default_empty,)
        return self.op(*args)

    def from_kwargs(
        self, columns_or_model: Union[Model, ColumnCollection], /, **kwargs: Any
    ) -> Any:
        if not isinstance(columns_or_model, ColumnCollection) and hasattr(
            columns_or_model, "columns"
        ):
            columns_or_model = columns_or_model.table.columns
        return self.op(*(getattr(columns_or_model, item[0]) == item[1] for item in kwargs.items()))


or_ = _EnhancedClausesHelper(sqlalchemy.or_, sqlalchemy.false())
or_.__doc__ = """
    Creates a SQL Alchemy OR clause for the expressions being passed.
"""
and_ = _EnhancedClausesHelper(sqlalchemy.and_, sqlalchemy.true())
and_.__doc__ = """
    Creates a SQL Alchemy AND clause for the expressions being passed.
"""

# alias
Q = and_


def not_(clause: Any) -> Any:
    """
    Creates a SQL Alchemy NOT clause for the expressions being passed.
    """
    return sqlalchemy.not_(clause)
