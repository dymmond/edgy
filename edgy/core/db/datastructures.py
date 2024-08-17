from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
    ClassVar,
    Dict,
    List,
    Optional,
    Sequence,
    Tuple,
    Type,
)

from pydantic import model_validator
from pydantic.dataclasses import dataclass

if TYPE_CHECKING:
    from edgy.core.db.models.types import BaseModelType

_empty_tuple: Tuple[Any, ...] = ()


@dataclass
class Index:
    """
    Class responsible for handling and declaring the database indexes.
    """

    suffix: str = "idx"
    __max_name_length__: ClassVar[int] = 63
    name: Optional[str] = None
    fields: Optional[Sequence[str]] = None

    @model_validator(mode="before")
    def validate_data(cls, values: Any) -> Any:
        name = values.kwargs.get("name")

        if name is not None and len(name) > cls.__max_name_length__:
            raise ValueError(
                f"The max length of the index name must be {cls.__max_name_length__}. Got {len(name)}"
            )

        fields = values.kwargs.get("fields")
        if not isinstance(fields, (tuple, list)):
            raise ValueError("Index.fields must be a list or a tuple.")

        if fields and not all(isinstance(field, str) for field in fields):
            raise ValueError("Index.fields must contain only strings with field names.")

        if name is None:
            suffix = values.kwargs.get("suffix", cls.suffix)
            values.kwargs["name"] = f"{suffix}_{'_'.join(fields)}"
        return values


@dataclass
class UniqueConstraint:
    """
    Class responsible for handling and declaring the database unique_together.
    """

    fields: List[str]
    name: Optional[str] = None
    __max_name_length__: ClassVar[int] = 63

    @model_validator(mode="before")
    def validate_data(cls, values: Any) -> Any:
        name = values.kwargs.get("name")

        if name is not None and len(name) > cls.__max_name_length__:
            raise ValueError(
                f"The max length of the constraint name must be {cls.__max_name_length__}. Got {len(name)}"
            )

        fields = values.kwargs.get("fields")
        if not isinstance(fields, (tuple, list)):
            raise ValueError("UniqueConstraint.fields must be a list or a tuple.")

        if fields and not all(isinstance(field, str) for field in fields):
            raise ValueError("UniqueConstraint.fields must contain only strings with field names.")

        return values


class QueryModelResultCache:
    """
    Class for caching query results.
    """

    def __init__(self) -> None:
        self._cache: Dict[str, Dict[Tuple[Any, ...], BaseModelType]] = {}

    def update(self, results: Sequence[BaseModelType]) -> None:
        for instance in results:
            try:
                cache_key = instance.create_cache_key(instance)
            except (AttributeError, KeyError):
                continue
            if len(cache_key) <= 1:
                continue
            _model_cache = self._cache.setdefault(instance.__class__.__name__, {})
            _model_cache[cache_key] = instance

    def get(self, model_class: Type[BaseModelType], row_or_model: Any) -> Optional[BaseModelType]:
        try:
            cache_key = model_class.create_cache_key(row_or_model)
        except (AttributeError, KeyError):
            return None
        _model_cache = self._cache.get(model_class.__name__)
        if _model_cache is None:
            return None
        entry = _model_cache.get(cache_key)
        if entry is None:
            return None
        return entry

    def get_or_cache_many(
        self,
        model_class: Type[BaseModelType],
        row_or_models: Sequence[Any],
        cache_fn: Callable[[Any], Optional[BaseModelType]],
    ) -> Optional[BaseModelType]:
        cache_update: List[BaseModelType] = []
        results: List[Optional[BaseModelType]] = []
        for row_or_model in row_or_models:
            result = self.get(model_class, row_or_model)
            if result is None:
                result = cache_fn(row_or_model)
                if result is not None:
                    cache_update.append(result)
                results.append(result)
        self.update(cache_update)
        return result

    async def aget_or_cache_many(
        self,
        model_class: Type[BaseModelType],
        row_or_models: Sequence[Any],
        cache_fn: Callable[[Any], Awaitable[Optional[BaseModelType]]],
    ) -> Optional[BaseModelType]:
        cache_update: List[BaseModelType] = []
        results: List[Optional[BaseModelType]] = []
        for row_or_model in row_or_models:
            result = self.get(model_class, row_or_model)
            if result is None:
                result = await cache_fn(row_or_model)
                if result is not None:
                    cache_update.append(result)
                results.append(result)
        self.update(cache_update)
        return result

    def all_for_model_class(self, model_class: Type[BaseModelType]) -> Sequence[BaseModelType]:
        _model_cache = self._cache.get(model_class.__name__)
        if _model_cache is None:
            return _empty_tuple
        return _model_cache.values()  # type: ignore
