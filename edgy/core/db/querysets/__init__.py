from typing import TYPE_CHECKING

from monkay import Monkay

if TYPE_CHECKING:
    from .clauses import Q, and_, not_, or_
    from .prefetch import Prefetch
    from .queryset import QuerySet

__all__ = ["QuerySet", "Q", "and_", "not_", "or_", "Prefetch"]

Monkay(
    globals(),
    lazy_imports={
        "QuerySet": ".queryset.QuerySet",
        "Q": ".clauses.Q",
        "and_": ".clauses.and_",
        "not_": ".clauses.not_",
        "or_": ".clauses.or_",
        "Prefetch": ".prefetch.Prefetch",
    },
)
