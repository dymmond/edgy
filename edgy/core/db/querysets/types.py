import typing
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Dict, Generator, List, Optional, Sequence, Set, Tuple, Union

if typing.TYPE_CHECKING:
    import sqlalchemy

    from edgy.core.db.models import Model

# Create a var type for the Edgy Model
EdgyModel = typing.TypeVar("EdgyModel", bound="Model")


class QueryType(ABC, typing.Generic[EdgyModel]):
    __slots__ = ("model_class",)

    def __init__(self, model_class: typing.Type[EdgyModel]) -> None:
        self.model_class: typing.Type[EdgyModel] = model_class

    def __class_getitem__(cls, *args: typing.Any, **kwargs: typing.Any) -> typing.Any:
        return cls

    @abstractmethod
    def filter(
        self, *clauses: Tuple["sqlalchemy.sql.expression.BinaryExpression", ...], **kwargs: Any
    ) -> "QueryType": ...

    @abstractmethod
    def all(self, clear_cache: bool = False) -> "QueryType": ...

    @abstractmethod
    def exclude(
        self, clauses: Tuple["sqlalchemy.sql.expression.BinaryExpression", ...], **kwargs: "Model"
    ) -> "QueryType": ...

    @abstractmethod
    def lookup(self, term: Any) -> "QueryType": ...

    @abstractmethod
    def order_by(self, columns: Union[List, str]) -> "QueryType": ...

    @abstractmethod
    def reverse(self) -> "QueryType": ...

    @abstractmethod
    def limit(self, limit_count: int) -> "QueryType": ...

    @abstractmethod
    def offset(self, offset: int) -> "QueryType": ...

    @abstractmethod
    def group_by(self, group_by: Union[List, str]) -> "QueryType": ...

    @abstractmethod
    def distinct(self, *distinct_on: Sequence[str]) -> "QueryType": ...

    @abstractmethod
    def select_related(self, related: Union[List, str]) -> "QueryType": ...

    @abstractmethod
    def only(self, *fields: Sequence[str]) -> "QueryType": ...

    @abstractmethod
    def defer(self, *fields: Sequence[str]) -> "QueryType": ...

    @abstractmethod
    async def exists(self) -> bool: ...

    @abstractmethod
    async def count(self) -> int: ...

    @abstractmethod
    async def get_or_none(self, **kwargs: Any) -> Union[EdgyModel, None]: ...

    @abstractmethod
    async def get(self, **kwargs: Any) -> EdgyModel: ...

    @abstractmethod
    async def first(self) -> Union[EdgyModel, None]: ...

    @abstractmethod
    async def last(self) -> Union[EdgyModel, None]: ...

    @abstractmethod
    async def create(self, **kwargs: Any) -> EdgyModel: ...

    @abstractmethod
    async def bulk_create(self, objs: Sequence[List[Dict[Any, Any]]]) -> None: ...

    @abstractmethod
    async def bulk_update(self, objs: Sequence[List[EdgyModel]], fields: List[str]) -> None: ...

    @abstractmethod
    async def delete(self) -> None: ...

    @abstractmethod
    async def update(self, **kwargs: Any) -> None: ...

    @abstractmethod
    async def values(
        self,
        fields: Union[Sequence[str], str, None],
        exclude: Union[Sequence[str], Set[str]],
        exclude_none: bool,
        flatten: bool,
        **kwargs: Any,
    ) -> List[Any]: ...

    @abstractmethod
    async def values_list(
        self,
        fields: Union[Sequence[str], str, None],
        exclude: Union[Sequence[str], Set[str]],
        exclude_none: bool,
        flat: bool,
    ) -> List[Any]: ...

    @abstractmethod
    async def get_or_create(
        self,
        _defaults: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Tuple[EdgyModel, bool]: ...

    @abstractmethod
    async def update_or_create(self, defaults: Any, **kwargs: Any) -> Tuple[EdgyModel, bool]: ...

    @abstractmethod
    async def contains(self, instance: EdgyModel) -> bool: ...

    @abstractmethod
    def __await__(self) -> Generator[Any, None, List[EdgyModel]]: ...

    @abstractmethod
    async def __aiter__(self) -> AsyncIterator[EdgyModel]: ...
