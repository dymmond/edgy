from __future__ import annotations

import sys
from collections.abc import Awaitable, Callable, Sequence
from typing import TYPE_CHECKING, Any, ClassVar

import sqlalchemy
from pydantic import ConfigDict, model_validator
from pydantic.dataclasses import dataclass

if sys.version_info >= (3, 11):  # pragma: no cover
    from typing import Self
else:  # pragma: no cover
    from typing_extensions import Self

if TYPE_CHECKING:
    from edgy.core.db.models.types import BaseModelType

_empty_tuple: tuple[Any, ...] = ()


@dataclass(config=ConfigDict(arbitrary_types_allowed=True))
class Index:
    """
    Class responsible for handling and declaring the database indexes.
    """

    suffix: str = "idx"
    __max_name_length__: ClassVar[int] = 63
    name: str | None = None
    fields: Sequence[str | sqlalchemy.TextClause] | None = None

    @model_validator(mode="before")
    def validate_data(cls, values: Any) -> Any:
        name = values.kwargs.get("name")

        if name is not None and len(name) > cls.__max_name_length__:
            raise ValueError(
                f"The max length of the index name must be {cls.__max_name_length__}. Got {len(name)}"
            )

        fields = values.kwargs.get("fields")
        if not isinstance(fields, tuple | list):
            raise ValueError("Index.fields must be a list or a tuple.")

        if fields and not all(isinstance(field, str | sqlalchemy.TextClause) for field in fields):
            raise ValueError(
                "Index.fields must contain only strings with field names or text() clauses."
            )

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
    name: str | None = None
    deferrable: bool | None = None
    initially: str | None = None
    __max_name_length__: ClassVar[int] = 63

    @model_validator(mode="before")
    def validate_data(cls, values: Any) -> Any:
        name = values.kwargs.get("name")

        if name is not None and len(name) > cls.__max_name_length__:
            raise ValueError(
                f"The max length of the constraint name must be {cls.__max_name_length__}. Got {len(name)}"
            )

        fields = values.kwargs.get("fields")
        if not isinstance(fields, tuple | list):
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
        prefix: str = "",
        cache: dict[str, dict[tuple[Any, ...], Any]] | None = None,
    ) -> None:
        if cache is None:
            cache = {}
        self.cache: dict[str, dict[tuple[Any, ...], Any]] = cache
        self.attrs = attrs
        self.prefix = prefix

    def create_category(self, model_class: type[BaseModelType], prefix: str | None = None) -> str:
        prefix = self.prefix if prefix is None else prefix
        return f"{prefix}_{model_class.__name__}"

    def create_sub_cache(self, attrs: Sequence[str], prefix: str = "") -> Self:
        return self.__class__(attrs, prefix=prefix, cache=self.cache)

    def clear(
        self, model_class: type[BaseModelType] | None = None, prefix: str | None = None
    ) -> None:
        cache: Any = self.cache
        if model_class is not None:
            cache = cache.get(self.create_category(model_class, prefix=prefix))
        if cache is not None:
            cache.clear()

    def create_cache_key(
        self,
        model_class: type[BaseModelType],
        instance: Any,
        attrs: Sequence[str] | None = None,
        prefix: str | None = None,
    ) -> tuple:
        """
        Build a cache key for the model.
        """
        # we don't know if we get a row, a dict or a model, so use model_class
        cache_key_list: list[Any] = [self.create_category(model_class, prefix=prefix)]
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

    def get_category(self, model_class: type[BaseModelType], prefix: str | None = None) -> dict:
        return self.cache.setdefault(self.create_category(model_class, prefix=prefix), {})

    def update(
        self,
        model_class: type[BaseModelType],
        values: Sequence[Any],
        cache_keys: Sequence[tuple] | None = None,
        prefix: str | None = None,
    ) -> None:
        if cache_keys is None:
            cache_keys = []
            for instance in values:
                try:
                    cache_key = self.create_cache_key(model_class, instance, prefix=prefix)
                except (AttributeError, KeyError):
                    cache_key = _empty_tuple
                cache_keys.append(cache_key)

        for cache_key, instance in zip(cache_keys, values, strict=False):
            if len(cache_key) <= 1:
                continue
            _category_cache = self.cache.setdefault(cache_key[0], {})
            _category_cache[cache_key] = instance

    def get_for_cache_key(
        self,
        cache_key: tuple,
        prefix: str | None = None,
        old_cache: QueryModelResultCache | None = None,
    ) -> Any | None:
        cache = self.cache if old_cache is None else old_cache.cache
        _category_cache = cache.get(cache_key[0])
        if _category_cache is None:
            return None
        entry = _category_cache.get(cache_key)
        if entry is None:
            return None
        if old_cache is not None:
            _category_cache = self.cache.setdefault(cache_key[0], {})
            _category_cache[cache_key] = entry
        return entry

    def get(
        self,
        model_class: type[BaseModelType],
        row_or_model: Any,
        prefix: str | None = None,
        old_cache: QueryModelResultCache | None = None,
    ) -> Any | None:
        try:
            cache_key = self.create_cache_key(model_class, row_or_model, prefix=prefix)
        except (AttributeError, KeyError):
            return None
        return self.get_for_cache_key(cache_key, prefix=prefix, old_cache=old_cache)

    def get_or_cache_many(
        self,
        model_class: type[BaseModelType],
        row_or_models: Sequence[Any],
        cache_fn: Callable[[Any], BaseModelType | None] | None = None,
        transform_fn: Callable[[BaseModelType | None], Any] | None = None,
        prefix: str | None = None,
        old_cache: QueryModelResultCache | None = None,
    ) -> Sequence[Any]:
        cache_update_keys: list[tuple] = []
        cache_update: list[BaseModelType] = []
        results: list[Any | None] = []
        for row_or_model in row_or_models:
            try:
                cache_key = self.create_cache_key(model_class, row_or_model, prefix=prefix)
            except (AttributeError, KeyError):
                # bypass
                result = row_or_model
                if cache_fn is not None:
                    result = cache_fn(row_or_model)
                if transform_fn is not None:
                    result = transform_fn(result)
                results.append(result)
                continue

            result = self.get_for_cache_key(cache_key, prefix=prefix, old_cache=old_cache)
            if result is None and cache_fn is not None:
                result = cache_fn(row_or_model)
                if result is not None:
                    cache_update_keys.append(cache_key)
                    if transform_fn is not None:
                        result = transform_fn(result)
                    cache_update.append(result)
            results.append(result)
        self.update(model_class, cache_update, cache_keys=cache_update_keys, prefix=prefix)
        return results

    async def aget_or_cache_many(
        self,
        model_class: type[BaseModelType],
        row_or_models: Sequence[Any],
        cache_fn: Callable[[Any], Awaitable[BaseModelType | None]] | None = None,
        transform_fn: Callable[[BaseModelType | None], Awaitable[Any]] | None = None,
        prefix: str | None = None,
        old_cache: QueryModelResultCache | None = None,
    ) -> Sequence[Any]:
        cache_update_keys: list[tuple] = []
        cache_update: list[Any] = []
        results: list[BaseModelType | None] = []
        for row_or_model in row_or_models:
            try:
                cache_key = self.create_cache_key(model_class, row_or_model, prefix=prefix)
            except (AttributeError, KeyError):
                # bypass
                result = row_or_model
                if cache_fn is not None:
                    result = await cache_fn(row_or_model)
                if transform_fn is not None:
                    result = await transform_fn(result)
                results.append(result)
                continue
            result = self.get_for_cache_key(cache_key, prefix=prefix, old_cache=old_cache)
            if result is None and cache_fn is not None:
                result = await cache_fn(row_or_model)
                if result is not None:
                    cache_update_keys.append(cache_key)
                    if transform_fn is not None:
                        result = await transform_fn(result)
                    cache_update.append(result)
            results.append(result)
        self.update(model_class, cache_update, cache_keys=cache_update_keys, prefix=prefix)
        return results
