from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    List,
    Optional,
    Sequence,
    Tuple,
    TypeVar,
    Union,
    runtime_checkable,
)

try:
    from typing import Protocol
except ImportError:  # pragma: nocover
    from typing_extensions import Protocol  # type: ignore


if TYPE_CHECKING:  # pragma: nocover
    from edgy import Model, QuerySet, ReflectModel


_EdgyModel = TypeVar("_EdgyModel", bound="Model")
ReflectEdgyModel = TypeVar("ReflectEdgyModel", bound="ReflectModel")

EdgyModel = Union[_EdgyModel, ReflectEdgyModel]


@runtime_checkable
class QuerySetProtocol(Protocol):
    """Defines the what needs to be implemented when using the ManyRelationProtocol"""

    def filter(self, **kwargs: Any) -> "QuerySet":
        ...

    def exclude(self, **kwargs: "Model") -> "QuerySet":
        ...

    def lookup(self, **kwargs: Any) -> "QuerySet":
        ...

    def order_by(self, columns: Union[List, str]) -> "QuerySet":
        ...

    def limit(self, limit_count: int) -> "QuerySet":
        ...

    def offset(self, offset: int) -> "QuerySet":
        ...

    def group_by(self, group_by: Union[List, str]) -> "QuerySet":
        ...

    def distinct(self, distinct_on: Union[List, str]) -> "QuerySet":
        ...

    def select_related(self, related: Union[List, str]) -> "QuerySet":
        ...

    def only(self, *fields: Sequence[str]) -> Union[List[EdgyModel], None]:
        ...

    async def exists(self) -> bool:
        ...

    async def count(self) -> int:
        ...

    async def get_or_none(self, **kwargs: Any) -> Union[EdgyModel, None]:
        ...

    async def all(self, **kwargs: Any) -> Sequence[Optional[EdgyModel]]:
        ...

    async def get(self, **kwargs: Any) -> EdgyModel:
        ...

    async def first(self, **kwargs: Any) -> EdgyModel:
        ...

    async def last(self, **kwargs: Any) -> EdgyModel:
        ...

    async def create(self, **kwargs: Any) -> EdgyModel:
        ...

    async def bulk_create(self, objs: Sequence[List[Dict[Any, Any]]]) -> None:
        ...

    async def bulk_update(self, objs: Sequence[List[EdgyModel]], fields: List[str]) -> None:
        ...

    async def delete(self) -> None:
        ...

    async def update(self, **kwargs: Any) -> int:
        ...

    async def values(self, fields: Sequence[str], flatten: bool) -> List[Any]:
        ...

    async def values_list(self, *fields: Sequence[str], flatten: bool) -> List[Any]:
        ...

    async def get_or_create(
        self,
        _defaults: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Tuple[EdgyModel, bool]:
        ...

    async def update_or_create(self, defaults: Any, **kwargs: Any) -> Tuple[EdgyModel, bool]:
        ...

    async def contains(self, instance: EdgyModel) -> bool:
        ...
