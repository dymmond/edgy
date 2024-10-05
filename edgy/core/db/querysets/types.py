from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Awaitable, Generator, Iterable, Sequence
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Generic,
    Literal,
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


class QueryType(ABC, Generic[EdgyEmbedTarget, EdgyModel]):
    __slots__ = ("model_class",)
    model_class: type[EdgyModel]

    def __init__(self, model_class: type[EdgyModel]) -> None:
        self.model_class = model_class

    @abstractmethod
    async def build_where_clause(self) -> Any: ...

    @abstractmethod
    def filter(
        self,
        *clauses: Union[
            "sqlalchemy.sql.expression.BinaryExpression",
            Callable[
                ["QueryType"],
                Union[
                    "sqlalchemy.sql.expression.BinaryExpression",
                    Awaitable["sqlalchemy.sql.expression.BinaryExpression"],
                ],
            ],
        ],
        **kwargs: Any,
    ) -> "QueryType": ...

    @abstractmethod
    def all(self, clear_cache: bool = False) -> "QueryType": ...

    @abstractmethod
    def or_(
        self,
        *clauses: Union[
            "sqlalchemy.sql.expression.BinaryExpression",
            Callable[
                ["QueryType"],
                Union[
                    "sqlalchemy.sql.expression.BinaryExpression",
                    Awaitable["sqlalchemy.sql.expression.BinaryExpression"],
                ],
            ],
        ],
        **kwargs: Any,
    ) -> "QueryType":
        """
        Filters the QuerySet by the OR operand.
        """

    @abstractmethod
    def and_(
        self,
        *clauses: Union[
            "sqlalchemy.sql.expression.BinaryExpression",
            Callable[
                ["QueryType"],
                Union[
                    "sqlalchemy.sql.expression.BinaryExpression",
                    Awaitable["sqlalchemy.sql.expression.BinaryExpression"],
                ],
            ],
        ],
        **kwargs: Any,
    ) -> "QueryType":
        """
        Filters the QuerySet by the AND operand. Alias of filter.
        """

    @abstractmethod
    def not_(
        self,
        *clauses: Union[
            "sqlalchemy.sql.expression.BinaryExpression",
            Callable[
                ["QueryType"],
                Union[
                    "sqlalchemy.sql.expression.BinaryExpression",
                    Awaitable["sqlalchemy.sql.expression.BinaryExpression"],
                ],
            ],
        ],
        **kwargs: Any,
    ) -> "QueryType":
        """
        Filters the QuerySet by the NOT operand. Alias of exclude.
        """
        raise NotImplementedError()

    @abstractmethod
    def exclude(
        self,
        *clauses: Union[
            "sqlalchemy.sql.expression.BinaryExpression",
            Callable[
                ["QueryType"],
                Union[
                    "sqlalchemy.sql.expression.BinaryExpression",
                    Awaitable["sqlalchemy.sql.expression.BinaryExpression"],
                ],
            ],
        ],
        **kwargs: Any,
    ) -> "QueryType": ...

    @abstractmethod
    def lookup(self, term: Any) -> "QueryType": ...

    @abstractmethod
    def order_by(self, *columns: Union[list, str]) -> "QueryType": ...

    @abstractmethod
    def reverse(self) -> "QueryType": ...

    @abstractmethod
    def limit(self, limit_count: int) -> "QueryType": ...

    @abstractmethod
    def offset(self, offset: int) -> "QueryType": ...

    @abstractmethod
    def group_by(self, group_by: Union[list, str]) -> "QueryType": ...

    @abstractmethod
    def distinct(self, *distinct_on: Sequence[str]) -> "QueryType": ...

    @abstractmethod
    def select_related(self, related: Union[list, str]) -> "QueryType": ...

    @abstractmethod
    def only(self, *fields: Sequence[str]) -> "QueryType": ...

    @abstractmethod
    def defer(self, *fields: Sequence[str]) -> "QueryType": ...

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
        flatten: bool,
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
    async def contains(self, instance: "BaseModelType") -> bool: ...

    @abstractmethod
    def transaction(self, *, force_rollback: bool = False, **kwargs: Any) -> "Transaction":
        """Return database transaction for the assigned database."""

    @abstractmethod
    def using(
        self,
        *,
        database: Union[str, Any, None, "Database"] = Undefined,
        schema: Union[str, Any, None, Literal[False]] = Undefined,
    ) -> "QueryType": ...

    @abstractmethod
    def __await__(self) -> Generator[Any, None, list[EdgyEmbedTarget]]: ...

    @abstractmethod
    async def __aiter__(self) -> AsyncIterator[EdgyEmbedTarget]: ...
