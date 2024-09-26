from __future__ import annotations

from collections.abc import Awaitable, Sequence
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    ClassVar,
    Optional,
)

from pydantic import model_validator
from pydantic.dataclasses import dataclass

if TYPE_CHECKING:
    from edgy.core.db.models.types import BaseModelType

_empty_tuple: tuple[Any, ...] = ()


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

    fields: list[str]
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

    def __init__(
        self,
        attrs: Sequence[str],
        prefix: str = "query",
        cache: Optional[dict[str, dict[tuple[Any, ...], Any]]] = None,
    ) -> None:
        if cache is None:
            cache = {}
        self.cache: dict[str, dict[tuple[Any, ...], Any]] = cache
        self.attrs = attrs

    def create_category(
        self, model_class: type[BaseModelType], prefix: Optional[str] = None
    ) -> str:
        return f"{prefix}_{model_class.__name__}"

    def create_sub_cache(
        self, attrs: Sequence[str], prefix: str = "query"
    ) -> QueryModelResultCache:
        return self.__class__(attrs, prefix=prefix, cache=self.cache)

    def clear(
        self, model_class: Optional[type[BaseModelType]] = None, prefix: Optional[str] = None
    ) -> None:
        cache: Any = self.cache
        if model_class is not None:
            cache = cache.get(self.create_category(model_class, prefix=prefix))
        if cache is not None:
            cache.clear()

    def create_cache_key(
        self, instance: Any, prefix: Optional[str] = None, attrs: Optional[Sequence[str]] = None
    ) -> tuple:
        """
        Build a cache key for the model.
        """
        cache_key_list: list[Any] = [self.create_category(type(instance), prefix=prefix)]
        if attrs is None:
            attrs = self.attrs
        # there are no columns, only column results
        if isinstance(instance, dict):
            for attr in attrs:
                cache_key_list.append(str(instance[attr]))
        else:
            for attr in self.attrs:
                cache_key_list.append(str(getattr(instance, attr)))
        return tuple(cache_key_list)

    def get_category(self, model_class: type[BaseModelType], prefix: Optional[str] = None) -> dict:
        return self.cache.setdefault(self.create_category(model_class, prefix=prefix), {})

    def update(self, values: Sequence[Any], cache_keys: Optional[Sequence[tuple]] = None) -> None:
        if cache_keys is None:
            cache_keys = []
            for instance in values:
                try:
                    cache_key = self.create_cache_key(instance)
                except (AttributeError, KeyError):
                    cache_key = _empty_tuple
                cache_keys.append(cache_key)

        for cache_key, instance in zip(cache_keys, values):
            if len(cache_key) <= 1:
                continue
            _category_cache = self.cache.setdefault(cache_key[0], {})
            _cache_list = _category_cache.setdefault(cache_key, [])
            _category_cache[cache_key] = instance

    def get(self, model_class: type[BaseModelType], row_or_model: Any) -> Optional[Any]:
        try:
            cache_key = self.create_cache_key(row_or_model)
        except (AttributeError, KeyError):
            return None
        _category_cache = self.cache.get(model_class.__name__)
        if _category_cache is None:
            return None
        entry = _category_cache.get(cache_key)
        if entry is None:
            return None
        return entry

    def get_or_cache_many(
        self,
        model_class: type[BaseModelType],
        row_or_models: Sequence[Any],
        cache_fn: Optional[Callable[[Any], Optional[BaseModelType]]] = None,
        transform_fn: Optional[Callable[[Optional[BaseModelType]], Any]] = None,
    ) -> Sequence[Any]:
        cache_update_keys: list[tuple] = []
        cache_update: list[BaseModelType] = []
        results: list[Optional[Any]] = []
        for row_or_model in row_or_models:
            result = self.get(model_class, row_or_model)
            if result is None and cache_fn is not None:
                result = cache_fn(row_or_model)
                if result is not None:
                    cache_update_keys.append(self.create_cache_key(result))
                    if transform_fn is not None:
                        result = transform_fn(result)
                    cache_update.append(result)
                results.append(result)
        self.update(cache_update, cache_keys=cache_update_keys)
        return results

    async def aget_or_cache_many(
        self,
        model_class: type[BaseModelType],
        row_or_models: Sequence[Any],
        cache_fn: Optional[Callable[[Any], Awaitable[Optional[BaseModelType]]]] = None,
        transform_fn: Optional[Callable[[Optional[BaseModelType]], Awaitable[Any]]] = None,
    ) -> Sequence[Any]:
        cache_update_keys: list[tuple] = []
        cache_update: list[Any] = []
        results: list[Optional[BaseModelType]] = []
        for row_or_model in row_or_models:
            result = self.get(model_class, row_or_model)
            if result is None:
                result = await cache_fn(row_or_model)
                if result is not None:
                    cache_update_keys.append(self.create_cache_key(result))
                    if transform_fn is not None:
                        result = await transform_fn(result)
                    cache_update.append(result)
                results.append(result)
        self.update(cache_update, cache_keys=cache_update_keys)
        return results
