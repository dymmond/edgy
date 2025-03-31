from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Awaitable, Generator, Iterable, Sequence
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Generic,
    Literal,
    Optional,
    TypeVar,
    Union,
)

from edgy.types import Undefined

if TYPE_CHECKING:
    import sqlalchemy
    from databasez.core.transaction import Transaction

    from edgy.core.connection import Database
    from edgy.core.db.models import BaseModelType

# Create a var type for the Edgy Model
EdgyModel = TypeVar("EdgyModel", bound="BaseModelType")
EdgyEmbedTarget = TypeVar("EdgyEmbedTarget")

tables_and_models_type = dict[str, tuple["sqlalchemy.Table", type["BaseModelType"]]]
reference_select_type = dict[
    str, Union[dict[str, "reference_select_type"], str, None, "sqlalchemy.Column"]
]


class QuerySetType(ABC, Generic[EdgyEmbedTarget, EdgyModel]):
    __slots__ = ("model_class",)
    model_class: type[EdgyModel]

    def __init__(self, model_class: type[EdgyModel]) -> None:
        self.model_class = model_class

    @abstractmethod
    async def build_where_clause(
        self, _: Any = None, tables_and_models: Optional[tables_and_models_type] = None
    ) -> Any: ...

    @abstractmethod
    def filter(
        self,
        *clauses: Union[
            sqlalchemy.sql.expression.BinaryExpression,
            Callable[
                [QuerySetType],
                Union[
                    sqlalchemy.sql.expression.BinaryExpression,
                    Awaitable[sqlalchemy.sql.expression.BinaryExpression],
                ],
            ],
            dict[str, Any],
            QuerySetType,
        ],
        **kwargs: Any,
    ) -> QuerySetType: ...

    @abstractmethod
    def all(self, clear_cache: bool = False) -> QuerySetType: ...

    @abstractmethod
    def or_(
        self,
        *clauses: Union[
            sqlalchemy.sql.expression.BinaryExpression,
            Callable[
                [QuerySetType],
                Union[
                    sqlalchemy.sql.expression.BinaryExpression,
                    Awaitable[sqlalchemy.sql.expression.BinaryExpression],
                ],
            ],
            QuerySetType,
        ],
        **kwargs: Any,
    ) -> QuerySetType:
        """
        Filters the QuerySet by the OR operand.
        """

    @abstractmethod
    def local_or(
        self,
        *clauses: Union[
            sqlalchemy.sql.expression.BinaryExpression,
            Callable[
                [QuerySetType],
                Union[
                    sqlalchemy.sql.expression.BinaryExpression,
                    Awaitable[sqlalchemy.sql.expression.BinaryExpression],
                ],
            ],
            QuerySetType,
        ],
        **kwargs: Any,
    ) -> QuerySetType:
        """
        Filters the QuerySet by the OR operand.
        """

    @abstractmethod
    def and_(
        self,
        *clauses: Union[
            sqlalchemy.sql.expression.BinaryExpression,
            Callable[
                [QuerySetType],
                Union[
                    sqlalchemy.sql.expression.BinaryExpression,
                    Awaitable[sqlalchemy.sql.expression.BinaryExpression],
                ],
            ],
            dict[str, Any],
            QuerySetType,
        ],
        **kwargs: Any,
    ) -> QuerySetType:
        """
        Filters the QuerySet by the AND operand. Alias of filter.
        """

    @abstractmethod
    def not_(
        self,
        *clauses: Union[
            sqlalchemy.sql.expression.BinaryExpression,
            Callable[
                [QuerySetType],
                Union[
                    sqlalchemy.sql.expression.BinaryExpression,
                    Awaitable[sqlalchemy.sql.expression.BinaryExpression],
                ],
            ],
            dict[str, Any],
            QuerySetType,
        ],
        **kwargs: Any,
    ) -> QuerySetType:
        """
        Filters the QuerySet by the NOT operand. Alias of exclude.
        """
        raise NotImplementedError()

    @abstractmethod
    def exclude(
        self,
        *clauses: Union[
            sqlalchemy.sql.expression.BinaryExpression,
            Callable[
                [QuerySetType],
                Union[
                    sqlalchemy.sql.expression.BinaryExpression,
                    Awaitable[sqlalchemy.sql.expression.BinaryExpression],
                ],
            ],
            dict[str, Any],
            QuerySetType,
        ],
        **kwargs: Any,
    ) -> QuerySetType: ...

    @abstractmethod
    def lookup(self, term: Any) -> QuerySetType: ...

    @abstractmethod
    def order_by(self, *columns: str) -> QuerySetType: ...

    @abstractmethod
    def reverse(self) -> QuerySetType: ...

    @abstractmethod
    def limit(self, limit_count: int) -> QuerySetType: ...

    @abstractmethod
    def offset(self, offset: int) -> QuerySetType: ...

    @abstractmethod
    def group_by(self, *group_by: str) -> QuerySetType: ...

    @abstractmethod
    def distinct(self, *distinct_on: Sequence[str]) -> QuerySetType: ...

    @abstractmethod
    def select_related(self, *related: str) -> QuerySetType: ...

    @abstractmethod
    def only(self, *fields: str) -> QuerySetType: ...

    @abstractmethod
    def defer(self, *fields: str) -> QuerySetType: ...

    @abstractmethod
    async def exists(self) -> bool: ...

    @abstractmethod
    async def count(self) -> int: ...

    @abstractmethod
    async def get_or_none(self, **kwargs: Any) -> Union[EdgyEmbedTarget, None]: ...

    @abstractmethod
    async def get(self, **kwargs: Any) -> EdgyEmbedTarget: ...

    @abstractmethod
    async def first(self) -> Union[EdgyEmbedTarget, None]: ...

    @abstractmethod
    async def last(self) -> Union[EdgyEmbedTarget, None]: ...

    @abstractmethod
    async def create(self, *args: Any, **kwargs: Any) -> EdgyEmbedTarget: ...

    @abstractmethod
    async def bulk_create(self, objs: Iterable[Union[dict[str, Any], EdgyModel]]) -> None: ...

    @abstractmethod
    async def bulk_update(self, objs: Sequence[EdgyModel], fields: list[str]) -> None: ...

    @abstractmethod
    async def delete(self) -> None: ...

    @abstractmethod
    async def update(self, **kwargs: Any) -> None: ...

    @abstractmethod
    async def values(
        self,
        fields: Union[Sequence[str], str, None],
        exclude: Union[Sequence[str], set[str]],
        exclude_none: bool,
        **kwargs: Any,
    ) -> list[Any]: ...

    @abstractmethod
    async def values_list(
        self,
        fields: Union[Sequence[str], str, None],
        exclude: Union[Sequence[str], set[str]],
        exclude_none: bool,
        flat: bool,
    ) -> list[Any]: ...

    @abstractmethod
    async def get_or_create(
        self,
        defaults: Union[dict[str, Any], Any, None] = None,
        *args: Any,
        **kwargs: Any,
    ) -> tuple[EdgyEmbedTarget, bool]: ...

    @abstractmethod
    async def update_or_create(
        self, defaults: Union[dict[str, Any], Any, None] = None, *args: Any, **kwargs: Any
    ) -> tuple[EdgyEmbedTarget, bool]: ...

    @abstractmethod
    async def contains(self, instance: BaseModelType) -> bool: ...

    @abstractmethod
    def transaction(self, *, force_rollback: bool = False, **kwargs: Any) -> Transaction:
        """Return database transaction for the assigned database."""

    @abstractmethod
    def using(
        self,
        *,
        database: Union[str, Any, None, Database] = Undefined,
        schema: Union[str, Any, None, Literal[False]] = Undefined,
    ) -> QuerySetType: ...

    @abstractmethod
    def extra_select(
        self,
        *extra: sqlalchemy.expression.ClauseElement,
    ) -> QuerySetType: ...

    @abstractmethod
    def reference_select(self, references: reference_select_type) -> QuerySetType: ...

    @abstractmethod
    def __await__(self) -> Generator[Any, None, list[EdgyEmbedTarget]]: ...

    @abstractmethod
    async def __aiter__(self) -> AsyncIterator[EdgyEmbedTarget]: ...


QueryType = QuerySetType
