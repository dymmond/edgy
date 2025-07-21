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

# An empty tuple used as a default for scenarios where no specific attributes are provided.
_empty_tuple: tuple[Any, ...] = ()


@dataclass(config=ConfigDict(arbitrary_types_allowed=True))
class Index:
    """
    Represents a database index, allowing for the declaration and configuration
    of indexes on model fields. Indexes are used to improve the performance
    of data retrieval operations.

    Attributes:
        suffix (str): The suffix appended to the index name if not explicitly provided.
                      Defaults to "idx".
        __max_name_length__ (ClassVar[int]): The maximum allowed length for an index name.
                                             Defaults to 63, a common limit in databases.
        name (str | None): The explicit name of the index. If None, a name will be
                           automatically generated based on the fields and suffix.
        fields (Sequence[str | sqlalchemy.TextClause] | None): A sequence of field names
                                                               or SQLAlchemy TextClause
                                                               objects on which the index
                                                               should be created.
    """

    suffix: str = "idx"
    __max_name_length__: ClassVar[int] = 63
    name: str | None = None
    fields: Sequence[str | sqlalchemy.TextClause] | None = None

    @model_validator(mode="before")
    @classmethod
    def validate_data(cls, values: Any) -> Any:
        """
        Pydantic model validator executed before data is assigned to the Index fields.
        It performs validation on the `name` and `fields` attributes and generates
        a default `name` if not provided.

        Args:
            values (Any): The input values for the Index instance.

        Returns:
            Any: The validated and potentially modified input values.

        Raises:
            ValueError:
                - If the provided `name` exceeds `__max_name_length__`.
                - If `fields` is not a list or tuple.
                - If `fields` contains elements that are not strings or `sqlalchemy.TextClause`.
        """
        # Retrieve the name from the input values, defaulting to None.
        name = values.kwargs.get("name")

        # Validate the length of the provided name.
        if name is not None and len(name) > cls.__max_name_length__:
            raise ValueError(
                f"The max length of the index name must be {cls.__max_name_length__}. "
                f"Got {len(name)}"
            )

        # Retrieve the fields from the input values.
        fields = values.kwargs.get("fields")
        # Validate that 'fields' is a list or a tuple.
        if not isinstance(fields, tuple | list):
            raise ValueError("Index.fields must be a list or a tuple.")

        # Validate that all elements in 'fields' are strings or SQLAlchemy TextClause objects.
        if fields and not all(isinstance(field, str | sqlalchemy.TextClause) for field in fields):
            raise ValueError(
                "Index.fields must contain only strings with field names or text() clauses."
            )

        # If no name is provided, generate a default name based on the suffix and fields.
        if name is None:
            suffix = values.kwargs.get("suffix", cls.suffix)
            values.kwargs["name"] = f"{suffix}_{'_'.join(fields)}"
        return values


@dataclass
class UniqueConstraint:
    """
    Represents a database unique constraint, ensuring that the combined values
    of specified fields are unique across all records in a table.

    Attributes:
        fields (list[str]): A list of field names that together form the unique constraint.
        name (str | None): The explicit name of the unique constraint. If None, a name will
                           be automatically generated.
        deferrable (bool | None): Specifies if the constraint check can be deferred.
                                  Defaults to None (database default).
        initially (str | None): Specifies when a deferrable constraint is checked.
                                Defaults to None (database default).
        __max_name_length__ (ClassVar[int]): The maximum allowed length for a constraint name.
                                             Defaults to 63.
    """

    fields: list[str]
    name: str | None = None
    deferrable: bool | None = None
    initially: str | None = None
    __max_name_length__: ClassVar[int] = 63

    @model_validator(mode="before")
    @classmethod
    def validate_data(cls, values: Any) -> Any:
        """
        Pydantic model validator executed before data is assigned to the UniqueConstraint fields.
        It performs validation on the `name` and `fields` attributes.

        Args:
            values (Any): The input values for the UniqueConstraint instance.

        Returns:
            Any: The validated input values.

        Raises:
            ValueError:
                - If the provided `name` exceeds `__max_name_length__`.
                - If `fields` is not a list or tuple.
                - If `fields` contains elements that are not strings.
        """
        # Retrieve the name from the input values, defaulting to None.
        name = values.kwargs.get("name")

        # Validate the length of the provided name.
        if name is not None and len(name) > cls.__max_name_length__:
            raise ValueError(
                f"The max length of the constraint name must be {cls.__max_name_length__}. "
                f"Got {len(name)}"
            )

        # Retrieve the fields from the input values.
        fields = values.kwargs.get("fields")
        # Validate that 'fields' is a list or a tuple.
        if not isinstance(fields, tuple | list):
            raise ValueError("UniqueConstraint.fields must be a list or a tuple.")

        # Validate that all elements in 'fields' are strings.
        if fields and not all(isinstance(field, str) for field in fields):
            raise ValueError("UniqueConstraint.fields must contain only strings with field names.")

        return values


class QueryModelResultCache:
    """
    A class designed for caching query results, particularly useful for optimizing
    repeated lookups of model instances that are frequently accessed. It allows
    caching based on specific model attributes (e.g., primary keys) and provides
    methods for creating, updating, and retrieving cached entries.
    """

    def __init__(
        self,
        attrs: Sequence[str],
        prefix: str = "",
        cache: dict[str, dict[tuple[Any, ...], Any]] | None = None,
    ) -> None:
        """
        Initializes a new QueryModelResultCache instance.

        Args:
            attrs (Sequence[str]): A sequence of attribute names that will be used
                                   to construct the cache key for model instances.
                                   These are typically primary key fields or unique
                                   identifiers.
            prefix (str): A string prefix to be added to the cache category name.
                          This helps in organizing caches, especially for different
                          types of queries or related models. Defaults to "".
            cache (dict[str, dict[tuple[Any, ...], Any]] | None): An optional
                                                                  pre-existing
                                                                  cache dictionary.
                                                                  If None, a new
                                                                  empty dictionary
                                                                  is created.
                                                                  Defaults to None.
        """
        if cache is None:
            cache = {}
        self.cache: dict[str, dict[tuple[Any, ...], Any]] = cache
        self.attrs = attrs
        self.prefix = prefix

    def create_category(self, model_class: type[BaseModelType], prefix: str | None = None) -> str:
        """
        Generates a cache category name based on the model class name and an optional prefix.
        This category acts as the top-level key in the `cache` dictionary.

        Args:
            model_class (type[BaseModelType]): The model class for which the category is being created.
            prefix (str | None): An optional prefix to use for the category. If None, the
                                 instance's default prefix is used. Defaults to None.

        Returns:
            str: The generated cache category name.
        """
        prefix = self.prefix if prefix is None else prefix
        return f"{prefix}_{model_class.__name__}"

    def create_sub_cache(self, attrs: Sequence[str], prefix: str = "") -> Self:
        """
        Creates a new `QueryModelResultCache` instance that shares the same underlying
        cache dictionary but uses different attributes for key generation or a different prefix.
        This is useful for creating specialized caches for different sets of attributes
        while leveraging a shared cache store.

        Args:
            attrs (Sequence[str]): The attributes to use for generating cache keys in the sub-cache.
            prefix (str): The prefix for the sub-cache's categories. Defaults to "".

        Returns:
            Self: A new `QueryModelResultCache` instance.
        """
        return self.__class__(attrs, prefix=prefix, cache=self.cache)

    def clear(
        self, model_class: type[BaseModelType] | None = None, prefix: str | None = None
    ) -> None:
        """
        Clears the cache. If a `model_class` is provided, only the cache for that
        specific model category is cleared. Otherwise, the entire cache is cleared.

        Args:
            model_class (type[BaseModelType] | None): The model class for which
                                                      to clear the cache. If None,
                                                      all cached entries are cleared.
                                                      Defaults to None.
            prefix (str | None): The prefix associated with the category to clear.
                                 If None, the instance's default prefix is used.
                                 Defaults to None.
        """
        cache: Any = self.cache
        if model_class is not None:
            # If a model class is provided, attempt to get its specific category cache.
            cache = cache.get(self.create_category(model_class, prefix=prefix))
        # If a valid cache (either specific or the whole cache) is found, clear it.
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
        Constructs a unique cache key for a given model instance. The key is a tuple
        consisting of the cache category and the string representation of the values
        of the specified attributes. This key is used to store and retrieve instances
        from the cache.

        Args:
            model_class (type[BaseModelType]): The model class of the instance.
            instance (Any): The model instance, which can be a dictionary (e.g., a row),
                            or a model object.
            attrs (Sequence[str] | None): The specific attributes to use for key generation.
                                         If None, the `attrs` defined during initialization
                                         of the cache are used. Defaults to None.
            prefix (str | None): The prefix for the cache category. If None, the
                                 instance's default prefix is used. Defaults to None.

        Returns:
            tuple: A unique tuple representing the cache key.
        """
        # we don't know if we get a row, a dict or a model, so use model_class
        cache_key_list: list[Any] = [self.create_category(model_class, prefix=prefix)]
        # Use the provided attrs or the instance's default attrs.
        if attrs is None:
            attrs = self.attrs
        # there are no columns, only column results

        # Iterate over the attributes and append their values to the cache key list.
        # This handles both dictionary-like instances (rows) and model objects.
        if isinstance(instance, dict):
            for attr in attrs:
                # Convert the value to string for consistent key generation.
                cache_key_list.append(str(instance[attr]))
        else:
            for attr in self.attrs:
                # Convert the value to string for consistent key generation.
                cache_key_list.append(str(getattr(instance, attr)))
        # Return the final cache key as a tuple.
        return tuple(cache_key_list)

    def get_category(self, model_class: type[BaseModelType], prefix: str | None = None) -> dict:
        """
        Retrieves or creates a dictionary representing the cache category for a given model class.
        This dictionary holds all cached entries for that specific model type.

        Args:
            model_class (type[BaseModelType]): The model class for which to get the category.
            prefix (str | None): The prefix for the cache category. If None, the
                                 instance's default prefix is used. Defaults to None.

        Returns:
            dict: The dictionary representing the cache category.
        """
        # Uses setdefault to get the category dictionary if it exists, or create it if not.
        return self.cache.setdefault(self.create_category(model_class, prefix=prefix), {})

    def update(
        self,
        model_class: type[BaseModelType],
        values: Sequence[Any],
        cache_keys: Sequence[tuple] | None = None,
        prefix: str | None = None,
    ) -> None:
        """
        Updates the cache with a sequence of model instances. For each instance,
        a cache key is generated (or provided), and the instance is stored in the cache.

        Args:
            model_class (type[BaseModelType]): The model class of the instances being updated.
            values (Sequence[Any]): A sequence of model instances (or rows) to be cached.
            cache_keys (Sequence[tuple] | None): An optional sequence of pre-generated
                                                 cache keys corresponding to the `values`.
                                                 If None, keys are generated dynamically.
                                                 Defaults to None.
            prefix (str | None): The prefix for the cache category. If None, the
                                 instance's default prefix is used. Defaults to None.
        """
        # If cache_keys are not provided, generate them for each instance.
        if cache_keys is None:
            cache_keys = []
            for instance in values:
                try:
                    # Attempt to create a cache key.
                    cache_key = self.create_cache_key(model_class, instance, prefix=prefix)
                except (AttributeError, KeyError):
                    # If key creation fails (e.g., missing attribute), use an empty tuple.
                    cache_key = _empty_tuple
                cache_keys.append(cache_key)

        # Iterate through cache keys and instances, updating the cache.
        for cache_key, instance in zip(cache_keys, values, strict=False):
            # Skip if the cache key is too short (e.g., it's an empty tuple due to an error).
            if len(cache_key) <= 1:
                continue
            # Get or create the category cache.
            _category_cache = self.cache.setdefault(cache_key[0], {})
            # Store the instance in the category cache using the full cache key.
            _category_cache[cache_key] = instance

    def get_for_cache_key(
        self,
        cache_key: tuple,
        prefix: str | None = None,
        old_cache: QueryModelResultCache | None = None,
    ) -> Any | None:
        """
        Retrieves a cached entry using a pre-generated cache key. If an `old_cache`
        is provided and the entry is found there, it is also populated into the
        current cache.

        Args:
            cache_key (tuple): The pre-generated tuple representing the cache key.
            prefix (str | None): The prefix for the cache category. If None, the
                                 instance's default prefix is used. Defaults to None.
            old_cache (QueryModelResultCache | None): An optional older cache instance
                                                     to check if the entry is not found
                                                     in the current cache. If found
                                                     in old_cache, it's copied to current.
                                                     Defaults to None.

        Returns:
            Any | None: The cached model instance, or None if not found.
        """
        # Determine which cache to use for retrieval.
        cache = self.cache if old_cache is None else old_cache.cache
        # Get the category cache based on the first element of the cache key.
        _category_cache = cache.get(cache_key[0])
        # If the category cache doesn't exist, return None.
        if _category_cache is None:
            return None
        # Retrieve the entry from the category cache.
        entry = _category_cache.get(cache_key)
        # If the entry is not found, return None.
        if entry is None:
            return None
        # If an old_cache was used and an entry was found, populate it into the current cache.
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
        """
        Retrieves a cached entry for a given model class and an instance (or row).
        It first attempts to create a cache key from the instance and then uses
        `get_for_cache_key` to retrieve the entry.

        Args:
            model_class (type[BaseModelType]): The model class of the instance.
            row_or_model (Any): The model instance or database row from which
                                to create the cache key.
            prefix (str | None): The prefix for the cache category. If None, the
                                 instance's default prefix is used. Defaults to None.
            old_cache (QueryModelResultCache | None): An optional older cache instance
                                                     to check if the entry is not found
                                                     in the current cache. Defaults to None.

        Returns:
            Any | None: The cached model instance, or None if not found or if
                        a cache key could not be generated.
        """
        try:
            # Attempt to create a cache key from the row or model.
            cache_key = self.create_cache_key(model_class, row_or_model, prefix=prefix)
        except (AttributeError, KeyError):
            # If key creation fails, return None.
            return None
        # Retrieve the entry using the generated cache key.
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
        """
        Synchronously retrieves multiple cached entries or populates the cache
        if entries are not found. It processes a sequence of rows or model instances,
        attempting to retrieve them from the cache. If an entry is not found, an
        optional `cache_fn` is called to create the model instance, which is then
        cached and potentially transformed by `transform_fn`.

        Args:
            model_class (type[BaseModelType]): The model class of the instances.
            row_or_models (Sequence[Any]): A sequence of database rows or model
                                           instances to process.
            cache_fn (Callable[[Any], BaseModelType | None] | None): An optional
                                                                     synchronous
                                                                     function that
                                                                     takes a row/model
                                                                     and returns
                                                                     a `BaseModelType`
                                                                     instance to cache.
                                                                     Defaults to None.
            transform_fn (Callable[[BaseModelType | None], Any] | None): An optional
                                                                        synchronous
                                                                        function to
                                                                        transform the
                                                                        cached model
                                                                        instance before
                                                                        returning it.
                                                                        Defaults to None.
            prefix (str | None): The prefix for the cache category. If None, the
                                 instance's default prefix is used. Defaults to None.
            old_cache (QueryModelResultCache | None): An optional older cache instance
                                                     to check if entries are not found
                                                     in the current cache. Defaults to None.

        Returns:
            Sequence[Any]: A sequence of cached or newly created and transformed instances.
        """
        cache_update_keys: list[tuple] = []
        cache_update: list[BaseModelType] = []
        results: list[Any | None] = []

        for row_or_model in row_or_models:
            try:
                # Attempt to create a cache key for the current row or model.
                cache_key = self.create_cache_key(model_class, row_or_model, prefix=prefix)
            except (AttributeError, KeyError):
                # If key creation fails (e.g., missing attribute), bypass caching for this item.
                result = row_or_model
                if cache_fn is not None:
                    result = cache_fn(row_or_model)
                if transform_fn is not None:
                    result = transform_fn(result)
                results.append(result)
                continue

            # Attempt to retrieve the result from the cache.
            result = self.get_for_cache_key(cache_key, prefix=prefix, old_cache=old_cache)
            if result is None and cache_fn is not None:
                # If not found and a cache_fn is provided, create the result.
                result = cache_fn(row_or_model)
                if result is not None:
                    # If a result is obtained, add its key and the result to the update lists.
                    cache_update_keys.append(cache_key)
                    if transform_fn is not None:
                        # Apply transformation if a transform_fn is provided.
                        result = transform_fn(result)
                    cache_update.append(result)
            results.append(result)
        # Update the cache with any newly created entries.
        self.update(model_class, cache_update, cache_keys=cache_update_keys, prefix=prefix)
        return results

    async def aget_or_cache_many(
        self,
        model_class: type[BaseModelType],
        row_or_models: Sequence[Any],
        cache_fn: Callable[[Any], Awaitable[BaseModelType | None]] | None = None,
        transform_fn: Callable[[BaseModelType | None], Awaitable[Any]] | None = None,
        prefix: str | None = None,
        old_cache: Self | None = None,
    ) -> Sequence[Any]:
        """
        Asynchronously retrieves multiple cached entries or populates the cache
        if entries are not found. This method is similar to `get_or_cache_many`
        but supports asynchronous `cache_fn` and `transform_fn`.

        Args:
            model_class (type[BaseModelType]): The model class of the instances.
            row_or_models (Sequence[Any]): A sequence of database rows or model
                                           instances to process.
            cache_fn (Callable[[Any], Awaitable[BaseModelType | None]] | None): An optional
                                                                               asynchronous
                                                                               function that
                                                                               takes a row/model
                                                                               and returns
                                                                               a `BaseModelType`
                                                                               instance to cache.
                                                                               Defaults to None.
            transform_fn (Callable[[BaseModelType | None], Awaitable[Any]] | None): An optional
                                                                                    asynchronous
                                                                                    function to
                                                                                    transform the
                                                                                    cached model
                                                                                    instance before
                                                                                    returning it.
                                                                                    Defaults to None.
            prefix (str | None): The prefix for the cache category. If None, the
                                 instance's default prefix is used. Defaults to None.
            old_cache (QueryModelResultCache | None): An optional older cache instance
                                                     to check if entries are not found
                                                     in the current cache. Defaults to None.

        Returns:
            Sequence[Any]: A sequence of cached or newly created and transformed instances.
        """
        cache_update_keys: list[tuple] = []
        cache_update: list[Any] = []
        results: list[BaseModelType | None] = []

        for row_or_model in row_or_models:
            try:
                # Attempt to create a cache key for the current row or model.
                cache_key = self.create_cache_key(model_class, row_or_model, prefix=prefix)
            except (AttributeError, KeyError):
                # If key creation fails, bypass caching for this item and process it directly.
                result = row_or_model
                if cache_fn is not None:
                    result = await cache_fn(row_or_model)
                if transform_fn is not None:
                    result = await transform_fn(result)
                results.append(result)
                continue

            # Attempt to retrieve the result from the cache.
            result = self.get_for_cache_key(cache_key, prefix=prefix, old_cache=old_cache)
            if result is None and cache_fn is not None:
                # If not found and an asynchronous cache_fn is provided, create the result.
                result = await cache_fn(row_or_model)
                if result is not None:
                    # If a result is obtained, add its key and the result to the update lists.
                    cache_update_keys.append(cache_key)
                    if transform_fn is not None:
                        # Apply asynchronous transformation if a transform_fn is provided.
                        result = await transform_fn(result)
                    cache_update.append(result)
            results.append(result)
        # Update the cache with any newly created entries.
        self.update(model_class, cache_update, cache_keys=cache_update_keys, prefix=prefix)
        return results
