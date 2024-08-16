from typing import (
    TYPE_CHECKING,
    Any,
    AsyncIterator,
    Dict,
    Generator,
    List,
    Optional,
    Protocol,
    Sequence,
    Set,
    Tuple,
    TypeVar,
    Union,
    runtime_checkable,
)

if TYPE_CHECKING:  # pragma: nocover
    import sqlalchemy

    from edgy import Model, QuerySet, ReflectModel


_EdgyModel = TypeVar("_EdgyModel", bound="Model")
ReflectEdgyModel = TypeVar("ReflectEdgyModel", bound="ReflectModel")

EdgyModel = Union[_EdgyModel, ReflectEdgyModel]


@runtime_checkable
class QuerySetProtocol(Protocol):
    """Defines the what needs to be implemented when using the QuerysetProtocol"""

    def filter(
        self, *clauses: Tuple["sqlalchemy.sql.expression.BinaryExpression", ...], **kwargs: Any
    ) -> "QuerySet": ...

    def all(self, **kwargs: Any) -> "QuerySet": ...

    def exclude(self, **kwargs: "Model") -> "QuerySet": ...

    def lookup(self, **kwargs: Any) -> "QuerySet": ...

    def order_by(self, columns: Union[List, str]) -> "QuerySet": ...

    def limit(self, limit_count: int) -> "QuerySet": ...

    def offset(self, offset: int) -> "QuerySet": ...

    def group_by(self, group_by: Union[List, str]) -> "QuerySet": ...

    def distinct(self, *distinct_on: Sequence[str]) -> "QuerySet": ...

    def select_related(self, related: Union[List, str]) -> "QuerySet": ...

    def only(self, *fields: Sequence[str]) -> "QuerySet": ...

    def defer(self, *fields: Sequence[str]) -> "QuerySet": ...

    async def exists(self) -> bool: ...

    async def count(self) -> int: ...

    async def get_or_none(self, **kwargs: Any) -> Union[EdgyModel, None]: ...

    async def get(self, **kwargs: Any) -> EdgyModel: ...

    async def first(self, **kwargs: Any) -> Union[EdgyModel, None]: ...

    async def last(self, **kwargs: Any) -> Union[EdgyModel, None]: ...

    async def create(self, **kwargs: Any) -> EdgyModel: ...

    async def bulk_create(self, objs: Sequence[List[Dict[Any, Any]]]) -> None: ...

    async def bulk_update(self, objs: Sequence[List[EdgyModel]], fields: List[str]) -> None: ...

    async def delete(self) -> None: ...

    async def update(self, **kwargs: Any) -> None: ...

    async def values(
        self,
        fields: Union[Sequence[str], str, None],
        exclude: Union[Sequence[str], Set[str]],
        exclude_none: bool,
        flatten: bool,
        **kwargs: Any,
    ) -> List[Any]: ...

    async def values_list(
        self,
        fields: Union[Sequence[str], str, None],
        exclude: Union[Sequence[str], Set[str]],
        exclude_none: bool,
        flat: bool,
    ) -> List[Any]: ...

    async def get_or_create(
        self,
        _defaults: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Tuple[EdgyModel, bool]: ...

    async def update_or_create(self, defaults: Any, **kwargs: Any) -> Tuple[EdgyModel, bool]: ...

    async def contains(self, instance: EdgyModel) -> bool: ...

    def __await__(self) -> Generator[Any, None, List[EdgyModel]]: ...

    async def __aiter__(self) -> AsyncIterator[EdgyModel]: ...
