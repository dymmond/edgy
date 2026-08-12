from __future__ import annotations

import sys
from abc import ABC, abstractmethod
from collections.abc import (
    AsyncIterator,
    Awaitable,
    Callable,
    Generator,
    Iterable,
    Sequence,
)
from typing import TYPE_CHECKING, Any, Generic, Literal, ParamSpec, TypeAlias, Union, overload

from edgy.types import Undefined

if TYPE_CHECKING:
    import sqlalchemy
    from databasez.core.transaction import Transaction

    from edgy.core.connection import Database
    from edgy.core.db.models.types import BaseModelType

if sys.version_info >= (3, 13):  # pragma: no cover
    from typing import TypeVar
else:  # pragma: no cover
    from typing_extensions import TypeVar

P = ParamSpec("P")

EdgyModel = TypeVar("EdgyModel", bound="BaseModelType")
"""
Type variable representing an Edgy BaseModelType.
"""
EdgyEmbedTarget = TypeVar("EdgyEmbedTarget", default=EdgyModel)
"""
Type variable representing the target type for embedded objects in a QuerySet.
"""

tables_and_models_type: TypeAlias = dict[str, tuple["sqlalchemy.Table", type["BaseModelType"]]]
"""
Type alias for a dictionary mapping table aliases to tuples containing a SQLAlchemy Table
and its corresponding BaseModelType.
"""
reference_select_type: TypeAlias = dict[
    str, Union[dict[str, "reference_select_type"], str, None, "sqlalchemy.Column"]
]
"""
Type alias for a dictionary representing a recursive structure used for selecting
references, allowing for nested selections, strings, None, or SQLAlchemy Columns.
"""


class QuerySetType(ABC, Generic[EdgyModel, EdgyEmbedTarget]):
    """
    Abstract base class defining the interface for all QuerySet operations in Edgy.

    This class specifies the methods that any QuerySet implementation must provide,
    ensuring a consistent API for database queries.
    """

    __slots__ = ("model_class",)
    model_class: type[EdgyModel]
    table: sqlalchemy.Table
    database: Database
    """
    The model class associated with this QuerySet.
    """

    def __init__(self, model_class: type[EdgyModel]) -> None:
        """
        Initializes the QuerySetType with a model class.

        Args:
            model_class (type[EdgyModel]): The model class for which this QuerySet operates.
        """
        self.model_class = model_class

    @abstractmethod
    async def build_where_clause(
        self, _: Any = None, tables_and_models: tables_and_models_type | None = None
    ) -> Any:
        """
        Abstract method to build the SQLAlchemy WHERE clause for the query.

        Args:
            _ (Any): Placeholder, typically ignored.
            tables_and_models (tables_and_models_type | None): A dictionary containing
                                                                SQLAlchemy tables and
                                                                their corresponding model types.

        Returns:
            Any: The SQLAlchemy WHERE clause expression.
        """
        ...

    @abstractmethod
    def filter(
        self,
        *clauses: sqlalchemy.sql.expression.BinaryExpression
        | Callable[
            [QuerySetType],
            sqlalchemy.sql.expression.BinaryExpression
            | Awaitable[sqlalchemy.sql.expression.BinaryExpression],
        ]
        | dict[str, Any]
        | QuerySetType,
        **kwargs: Any,
    ) -> QuerySetType[EdgyModel, EdgyEmbedTarget]:
        """
        Abstract method to filter the QuerySet based on provided clauses or keyword arguments.

        Args:
            *clauses: Positional arguments representing filter conditions. These can be
                      SQLAlchemy binary expressions, callables that return expressions,
                      dictionaries of field-value pairs, or other QuerySet instances.
            **kwargs: Keyword arguments representing field-value pairs for filtering.

        Returns:
            QuerySetType: A new QuerySet instance with the applied filters.
        """
        ...

    @abstractmethod
    def all(self, clear_cache: bool = False) -> QuerySetType[EdgyModel, EdgyEmbedTarget]:
        """
        Abstract method to return a QuerySet representing all objects of the model.

        Args:
            clear_cache (bool): If True, clears any cached results for the QuerySet.

        Returns:
            QuerySetType: A new QuerySet instance representing all objects.
        """
        ...

    @abstractmethod
    def or_(
        self,
        *clauses: sqlalchemy.sql.expression.BinaryExpression
        | Callable[
            [QuerySetType],
            sqlalchemy.sql.expression.BinaryExpression
            | Awaitable[sqlalchemy.sql.expression.BinaryExpression],
        ]
        | QuerySetType,
        **kwargs: Any,
    ) -> QuerySetType[EdgyModel, EdgyEmbedTarget]:
        """
        Filters the QuerySet by the OR operand.

        Abstract method to apply an OR condition to the QuerySet's filters.

        Args:
            *clauses: Positional arguments representing OR conditions. These can be
                      SQLAlchemy binary expressions, callables that return expressions,
                      or other QuerySet instances.
            **kwargs: Keyword arguments representing field-value pairs for OR filtering.

        Returns:
            QuerySetType: A new QuerySet instance with the OR condition applied.
        """

    @abstractmethod
    def local_or(
        self,
        *clauses: sqlalchemy.sql.expression.BinaryExpression
        | Callable[
            [QuerySetType],
            sqlalchemy.sql.expression.BinaryExpression
            | Awaitable[sqlalchemy.sql.expression.BinaryExpression],
        ]
        | QuerySetType,
        **kwargs: Any,
    ) -> QuerySetType[EdgyModel, EdgyEmbedTarget]:
        """
        Filters the QuerySet by the OR operand.

        Abstract method to apply an OR condition locally to the QuerySet's filters.
        This might differ from `or_` in how it interacts with global filters.

        Args:
            *clauses: Positional arguments representing OR conditions. These can be
                      SQLAlchemy binary expressions, callables that return expressions,
                      or other QuerySet instances.
            **kwargs: Keyword arguments representing field-value pairs for local OR filtering.

        Returns:
            QuerySetType: A new QuerySet instance with the local OR condition applied.
        """

    @abstractmethod
    def and_(
        self,
        *clauses: sqlalchemy.sql.expression.BinaryExpression
        | Callable[
            [QuerySetType],
            sqlalchemy.sql.expression.BinaryExpression
            | Awaitable[sqlalchemy.sql.expression.BinaryExpression],
        ]
        | dict[str, Any]
        | QuerySetType,
        **kwargs: Any,
    ) -> QuerySetType[EdgyModel, EdgyEmbedTarget]:
        """
        Filters the QuerySet by the AND operand. Alias of filter.

        Abstract method to apply an AND condition to the QuerySet's filters.
        This method behaves similarly to `filter`.

        Args:
            *clauses: Positional arguments representing AND conditions. These can be
                      SQLAlchemy binary expressions, callables that return expressions,
                      dictionaries of field-value pairs, or other QuerySet instances.
            **kwargs: Keyword arguments representing field-value pairs for AND filtering.

        Returns:
            QuerySetType: A new QuerySet instance with the AND condition applied.
        """

    @abstractmethod
    def not_(
        self,
        *clauses: sqlalchemy.sql.expression.BinaryExpression
        | Callable[
            [QuerySetType],
            sqlalchemy.sql.expression.BinaryExpression
            | Awaitable[sqlalchemy.sql.expression.BinaryExpression],
        ]
        | dict[str, Any]
        | QuerySetType,
        **kwargs: Any,
    ) -> QuerySetType[EdgyModel, EdgyEmbedTarget]:
        """
        Filters the QuerySet by the NOT operand. Alias of exclude.

        Abstract method to apply a NOT condition to the QuerySet's filters,
        effectively excluding results that match the criteria.
        This method behaves similarly to `exclude`.

        Args:
            *clauses: Positional arguments representing NOT conditions. These can be
                      SQLAlchemy binary expressions, callables that return expressions,
                      dictionaries of field-value pairs, or other QuerySet instances.
            **kwargs: Keyword arguments representing field-value pairs for NOT filtering.

        Returns:
            QuerySetType: A new QuerySet instance with the NOT condition applied.
        """
        raise NotImplementedError()

    @abstractmethod
    def exclude(
        self,
        *clauses: sqlalchemy.sql.expression.BinaryExpression
        | Callable[
            [QuerySetType],
            sqlalchemy.sql.expression.BinaryExpression
            | Awaitable[sqlalchemy.sql.expression.BinaryExpression],
        ]
        | dict[str, Any]
        | QuerySetType,
        **kwargs: Any,
    ) -> QuerySetType[EdgyModel, EdgyEmbedTarget]:
        """
        Abstract method to exclude objects from the QuerySet based on provided clauses or keyword arguments.

        Args:
            *clauses: Positional arguments representing exclusion conditions. These can be
                      SQLAlchemy binary expressions, callables that return expressions,
                      dictionaries of field-value pairs, or other QuerySet instances.
            **kwargs: Keyword arguments representing field-value pairs for exclusion.

        Returns:
            QuerySetType: A new QuerySet instance with the applied exclusions.
        """
        ...

    @abstractmethod
    def lookup(self, term: Any) -> QuerySetType[EdgyModel, EdgyEmbedTarget]:
        """
        Abstract method to perform a generic lookup on the QuerySet.

        The exact behavior of this method depends on the concrete implementation.

        Args:
            term (Any): The term to look up.

        Returns:
            QuerySetType: A new QuerySet instance with the lookup applied.
        """
        ...

    @abstractmethod
    def order_by(self, *columns: str) -> QuerySetType[EdgyModel, EdgyEmbedTarget]:
        """
        Abstract method to order the QuerySet results by one or more columns.

        Args:
            *columns (str): Column names to order by. Prefix with '-' for descending order.

        Returns:
            QuerySetType: A new QuerySet instance with the specified ordering.
        """
        ...

    @abstractmethod
    def reverse(self) -> QuerySetType[EdgyModel, EdgyEmbedTarget]:
        """
        Abstract method to reverse the current ordering of the QuerySet.

        Returns:
            QuerySetType: A new QuerySet instance with reversed ordering.
        """
        ...

    @abstractmethod
    def limit(self, limit_count: int) -> QuerySetType[EdgyModel, EdgyEmbedTarget]:
        """
        Abstract method to limit the number of results returned by the QuerySet.

        Args:
            limit_count (int): The maximum number of results to return.

        Returns:
            QuerySetType: A new QuerySet instance with the limit applied.
        """
        ...

    @abstractmethod
    def offset(self, offset: int) -> QuerySetType[EdgyModel, EdgyEmbedTarget]:
        """
        Abstract method to set the offset for the QuerySet results.

        Args:
            offset (int): The number of rows to skip from the beginning of the result set.

        Returns:
            QuerySetType: A new QuerySet instance with the offset applied.
        """
        ...

    @abstractmethod
    def group_by(self, *group_by: str) -> QuerySetType[EdgyModel, EdgyEmbedTarget]:
        """
        Abstract method to group the QuerySet results by one or more columns.

        Args:
            *group_by (str): Column names to group by.

        Returns:
            QuerySetType: A new QuerySet instance with the specified grouping.
        """
        ...

    @abstractmethod
    def distinct(
        self, first: bool | str = True, /, *distinct_on: str
    ) -> QuerySetType[EdgyModel, EdgyEmbedTarget]:
        """
        Abstract method to select distinct rows based on specific columns or all columns.

        Args:
            *distinct_on (Sequence[str]): Optional. Sequences of column names on which
                                           to apply the DISTINCT ON clause. If empty,
                                           applies DISTINCT to all selected columns.

        Returns:
            QuerySetType: A new QuerySet instance with the distinct clause applied.
        """
        ...

    @abstractmethod
    def select_related(self, *related: str) -> QuerySetType[EdgyModel, EdgyEmbedTarget]:
        """
        Abstract method to perform an eager load of related objects using SQL JOINs.

        Args:
            *related (str): Relationship names to eager load. Supports '__' for nested relationships.

        Returns:
            QuerySetType: A new QuerySet instance with eager loading configured.
        """
        ...

    @abstractmethod
    def only(self, *fields: str) -> QuerySetType[EdgyModel, EdgyEmbedTarget]:
        """
        Abstract method to select only a specific set of fields from the model.

        Args:
            *fields (str): Names of the fields to include in the query results.

        Returns:
            QuerySetType: A new QuerySet instance selecting only the specified fields.
        """
        ...

    @abstractmethod
    def defer(self, *fields: str) -> QuerySetType[EdgyModel, EdgyEmbedTarget]:
        """
        Abstract method to defer the loading of specific fields from the model.

        These fields will not be loaded when the main query is executed but can be
        loaded later if accessed.

        Args:
            *fields (str): Names of the fields to defer.

        Returns:
            QuerySetType: A new QuerySet instance with the specified fields deferred.
        """
        ...

    @overload
    def update_embed_parent(self, embed_parent: None) -> QuerySetType[EdgyModel, EdgyModel]: ...
    @overload
    def update_embed_parent(
        self, embed_parent: tuple[str, str]
    ) -> QuerySetType[EdgyModel, EdgyEmbedTarget]: ...
    @abstractmethod
    def update_embed_parent(
        self, embed_parent: tuple[str, str] | None
    ) -> QuerySetType[EdgyModel, EdgyEmbedTarget] | QuerySetType[EdgyModel, EdgyModel]:
        """
        Abstract method to update or remove (provide None) embed_parent applied on instances.
        Note: this doesn't affect embed_parent for filters.

        Args:
            embed_parent: define the new embed_parent.
        Returns:
            QuerySetType: A new QuerySet instance with the new embedding.
        """
        ...

    @abstractmethod
    async def exists(self) -> bool:
        """
        Abstract method to check if any objects matching the QuerySet criteria exist.

        Returns:
            bool: True if at least one object exists, False otherwise.
        """
        ...

    @abstractmethod
    async def count(self) -> int:
        """
        Abstract method to get the total number of objects matching the QuerySet criteria.

        Returns:
            int: The count of matching objects.
        """
        ...

    @abstractmethod
    async def get_or_none(self, **kwargs: Any) -> EdgyEmbedTarget | None:
        """
        Abstract method to retrieve a single object matching the given criteria, or None if not found.

        Args:
            **kwargs: Keyword arguments for filtering the object.

        Returns:
            EdgyEmbedTarget | None: The matching object, or None if no object is found.
        """
        ...

    @abstractmethod
    async def get(self, **kwargs: Any) -> EdgyEmbedTarget:
        """
        Abstract method to retrieve a single object matching the given criteria.

        Raises `ObjectNotFound` if no object is found, or `MultipleObjectsReturned`
        if more than one object matches.

        Args:
            **kwargs: Keyword arguments for filtering the object.

        Returns:
            EdgyEmbedTarget: The matching object.
        """
        ...

    @abstractmethod
    async def first(self) -> EdgyEmbedTarget | None:
        """
        Abstract method to retrieve the first object from the QuerySet, or None if the QuerySet is empty.

        Returns:
            EdgyEmbedTarget | None: The first object, or None.
        """
        ...

    @abstractmethod
    async def last(self) -> EdgyEmbedTarget | None:
        """
        Abstract method to retrieve the last object from the QuerySet, or None if the QuerySet is empty.

        Returns:
            EdgyEmbedTarget | None: The last object, or None.
        """
        ...

    @abstractmethod
    async def create(self, *args: Any, **kwargs: Any) -> EdgyEmbedTarget:
        """
        Abstract method to create and save a new object in the database.

        Args:
            *args: Positional arguments for object creation.
            **kwargs: Keyword arguments for object creation (e.g., field values).

        Returns:
            EdgyEmbedTarget: The newly created object instance.
        """
        ...

    @overload
    async def bulk_create(
        self,
        objs: Iterable[dict[str, Any] | EdgyModel],
        *,
        ignore_conflicts: bool = False,
        resolve_embed: Literal[True],
    ) -> list[EdgyEmbedTarget | None]:
        """
        Args:
            ...
            resolve_embed (True): Enables embedding.

        Returns:
            list[EdgyEmbedTarget | None]: A list of created objects.
                                   Warning: Instances which are not compatible (`can_load` is False)
                                   will execute an extra save.
        """

    @overload
    async def bulk_create(
        self,
        objs: Iterable[dict[str, Any] | EdgyModel],
        *,
        ignore_conflicts: bool = False,
        resolve_embed: Literal[False] = False,
    ) -> list[EdgyModel | None]:
        """
        Args:
            ...
            resolve_embed (False): Disables embedding. Default.
        Returns:
            list[EdgyModel | None]: A list of created objects.
                             Warning: for performance reasons no embedding is applied and
                             the returned objects are maybe incomplete (check `can_load` property).
        """

    @abstractmethod
    async def bulk_create(
        self,
        objs: Iterable[dict[str, Any] | EdgyModel],
        *,
        ignore_conflicts: bool = False,
        resolve_embed: bool = False,
    ) -> list[EdgyModel | None] | list[EdgyEmbedTarget | None]:
        """
        Abstract method to create multiple objects in a single bulk operation.

        Args:
            objs (Iterable[dict[str, Any] | EdgyModel]): An iterable of dictionaries or
                                                         model instances to create.
        Kwargs:
            ignore_conflicts (bool): Ignore insert conflicts. Support varies between database systems.
            resolve_embed (bool): Triggers mode in which embedding is applied when True.

        Returns:
            list[EdgyModel | None] | list[EdgyEmbedTarget | None]:
                A list of created objects.
                Warning: for performance reasons no embedding is applied by default and
                the returned objects are maybe incomplete (check `can_load` property).
        """
        ...

    @overload
    async def bulk_update(
        self,
        objs: Iterable[EdgyModel | dict[str, Any]],
        *,
        update_fields: Iterable[str] | None = None,
        unique_fields: Iterable[str] | None = None,
        resolve_embed: Literal[True],
    ) -> list[EdgyEmbedTarget | None]:
        """
        Kwargs:
            ...
            resolve_embed (True): Enables embedding.

        Returns:
            list[EdgyEmbedTarget | None]: A list of updated objects.
                                   Warning: All models must be loadable (`can_load` property is true)
                                   otherwise an `QuerySetError` is raised.
        """

    @overload
    async def bulk_update(
        self,
        objs: Iterable[EdgyModel | dict[str, Any]],
        *,
        update_fields: Iterable[str] | None = None,
        unique_fields: Iterable[str] | None = None,
        resolve_embed: Literal[False] = False,
    ) -> list[EdgyModel | None]:
        """
        Kwargs:
            ...
            resolve_embed (False): Disables embedding. Default.
        Returns:
            list[EdgyModel | None]: A list of updated objects.
                             Warning: for performance reasons no embedding is applied and
                             the returned objects are maybe incomplete (check `can_load` property).
        """

    @abstractmethod
    async def bulk_update(
        self,
        objs: Iterable[EdgyModel | dict[str, Any]],
        *,
        update_fields: Iterable[str] | None = None,
        unique_fields: Iterable[str] | None = None,
        resolve_embed: bool = False,
    ) -> list[EdgyModel | None] | list[EdgyEmbedTarget | None]:
        """
        Abstract method to update multiple objects in a single bulk operation.

        Args:
            objs (Iterable[EdgyModel | dict[str, Any]]): A sequence of model instances to update.
        Kwargs:
            update_fields (Iterable[str]): A list of field names to update for each object. If None use all fields.
            unique_fields (Iterable[str] | None): Fields that determine uniqueness.
                                                    If None, pknames are used. If empty it fails.
            resolve_embed (bool): Triggers mode in which embedding is applied when True.

        Returns:
            list[EdgyModel | None] | list[EdgyEmbedTarget | None]:
                A list of updated objects.
                Warning: for performance reasons no embedding is applied by default and
                the returned objects are maybe incomplete (check `can_load` property).
                When an input doesn't succeed in creating an update `None` is used as placeholder.
        """
        ...

    @overload
    async def bulk_update_or_create(
        self,
        objs: Iterable[dict[str, Any] | EdgyModel],
        *,
        update_fields: Iterable[str] | None = None,
        unique_fields: Iterable[str] | None = None,
        resolve_embed: Literal[True],
    ) -> list[tuple[EdgyEmbedTarget | None, bool]]:
        """
        Kwargs:
            ...
            resolve_embed (True): Enables embedding.

        Returns:
            list[tuple[EdgyEmbedTarget | None, bool]]: A list of `(instance, created)` tuples.
                                                Warning: All models must be loadable (`can_load` property is true)
                                                otherwise an `QuerySetError` is raised.
        """

    @overload
    async def bulk_update_or_create(
        self,
        objs: Iterable[dict[str, Any] | EdgyModel],
        *,
        update_fields: Iterable[str] | None = None,
        unique_fields: Iterable[str] | None = None,
        resolve_embed: Literal[False] = False,
    ) -> list[tuple[EdgyModel | None, bool]]:
        """
        Kwargs:
            ...
            resolve_embed (False): Disables embedding. Default.
        Returns:
            list[tuple[EdgyModel | None, bool]]: A list of tuples with updated or created objects and  created flag.
                                          Warning: for performance reasons no embedding is applied and
                                          the returned objects are maybe incomplete (check `can_load` property).
        """

    @abstractmethod
    async def bulk_update_or_create(
        self,
        objs: Iterable[dict[str, Any] | EdgyModel],
        *,
        update_fields: Iterable[str] | None = None,
        unique_fields: Iterable[str] | None = None,
        resolve_embed: bool = False,
    ) -> list[tuple[EdgyModel | None, bool]] | list[tuple[EdgyEmbedTarget | None, bool]]:
        """
        Abstract method to bulk updates or creates records in a table.

        If records exist based on unique fields, they are retrieved.
        Otherwise, new records are created.

        Args:
            objs (Sequence[Union[dict[str, Any], EdgyModel]]): A list of objects or dictionaries.
        Kwargs:
            update_fields (Iterable[str]): A list of field names to update for each object (when found).
                                    If None use all fields.
            unique_fields (Iterable[str] | None): Fields that determine uniqueness.
                                                  If None, pknames are used. If empty it fails.
            resolve_embed (bool): Triggers mode in which embedding is applied when True.

        Returns:
            list[tuple[EdgyModel | None, bool]] | list[tuple[EdgyEmbedTarget | None, bool]]:
                A list of `(instance, created)` tuples.
                Warning: for performance reasons no embedding is applied by default and
                the returned objects are maybe incomplete (check `can_load` property).
                `None` is returned for insert conflicts where no update could be generated.
        """
        ...

    @overload
    async def bulk_get_or_create(
        self,
        objs: Iterable[dict[str, Any] | EdgyModel],
        *,
        unique_fields: Iterable[str] | None = None,
        resolve_embed: Literal[True],
    ) -> list[tuple[EdgyEmbedTarget | None, bool]]:
        """
        Kwargs:
            ...
            resolve_embed (True): Enables embedding.

        Returns:
            list[tuple[EdgyEmbedTarget | None, bool]]: A list of `(instance, created)` tuples.
                                                Warning: Instances which are not compatible (`can_load` is False)
                                                will execute an extra save.
        """

    @overload
    async def bulk_get_or_create(
        self,
        objs: Iterable[dict[str, Any] | EdgyModel],
        *,
        unique_fields: Iterable[str] | None = None,
        resolve_embed: Literal[False] = False,
    ) -> list[tuple[EdgyModel | None, bool]]:
        """
        Kwargs:
            ...
            resolve_embed (False): Disables embedding. Default.
        Returns:
            list[tuple[EdgyModel | None, bool]]: A list of `(instance, created)` tuples.
                                          Warning: for performance reasons no embedding is applied and
                                          the returned objects are maybe incomplete (check `can_load` property).
        """

    @abstractmethod
    async def bulk_get_or_create(
        self,
        objs: Iterable[dict[str, Any] | EdgyModel],
        *,
        unique_fields: Iterable[str] | None = None,
        resolve_embed: bool = False,
    ) -> list[tuple[EdgyModel | None, bool]] | list[tuple[EdgyEmbedTarget | None, bool]]:
        """
        Abstract method to bulk get or create records in a table.

        If records exist based on unique fields, they are retrieved.
        Otherwise, new records are created.

        Args:
            objs (Iterable[Union[dict[str, Any], EdgyModel]]): A list of objects or dictionaries.
        Kwargs:
            unique_fields (Iterable[str] | None): Fields that determine uniqueness.
                                                  If None, pknames are used. If empty it fails.
            resolve_embed (bool): Triggers mode in which embedding is applied when True.

        Returns:
            list[tuple[EdgyModel | None, bool]] | list[tuple[EdgyEmbedTarget | None, bool]]:
                A list of tuples with retrieved or newly created objects and created flag.
                Warning: for performance reasons no embedding is applied by default and
                the returned objects are maybe incomplete (check `can_load` property).
        """
        ...

    bulk_select_or_insert = bulk_get_or_create

    @abstractmethod
    async def delete(self) -> int:
        """
        Abstract method to delete all objects matching the QuerySet criteria from the database.
        """
        ...

    @abstractmethod
    async def update(self, **kwargs: Any) -> int | None:
        """
        Abstract method to update fields for all objects matching the QuerySet criteria.

        Args:
            **kwargs: Keyword arguments representing the fields and their new values to update.
        Returns:
            int | None: Amount of rows changed if known for the database.
        """
        ...

    @abstractmethod
    async def values(
        self,
        fields: Sequence[str] | str | None,
        exclude: Sequence[str] | set[str] | None,
        exclude_none: bool = False,
    ) -> list[Any]:
        """
        Abstract method to return a list of dictionaries, where each dictionary represents
        an object and contains only the specified fields.

        Args:
            fields (Sequence[str] | str | None): Fields to include in the result. Can be
                                                 a sequence of strings, a single string, or None for all.
            exclude (Sequence[str] | set[str]): Fields to exclude from the result.
            exclude_none (bool): If True, excludes fields with None values from the result.

        Returns:
            list[Any]: A list of dictionaries representing the selected values.
        """
        ...

    @abstractmethod
    async def values_list(
        self,
        fields: Sequence[str] | str | None,
        exclude: Sequence[str] | set[str] | None,
        exclude_none: bool = False,
        flat: bool = False,
    ) -> list[Any]:
        """
        Abstract method to return a list of tuples, where each tuple contains
        the values of the specified fields.

        Args:
            fields (Sequence[str] | str | None): Fields to include in the result. Can be
                                                 a sequence of strings, a single string, or None for all.
            exclude (Sequence[str] | set[str]): Fields to exclude from the result.
            exclude_none (bool): If True, excludes fields with None values from the result.
            flat (bool): If True and only one field is specified, returns a flat list
                         instead of a list of single-element tuples.

        Returns:
            list[Any]: A list of tuples or a flat list representing the selected values.
        """
        ...

    @abstractmethod
    async def get_or_create(
        self,
        defaults: dict[str, Any] | Any | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> tuple[EdgyEmbedTarget, bool]:
        """
        Abstract method to retrieve an object, or create it if it does not exist.

        Args:
            defaults (dict[str, Any] | Any | None): A dictionary of default values to use
                                                     when creating the object if it doesn't exist.
            *args: Positional arguments for object creation if needed.
            **kwargs: Lookup parameters to find the object. If not found, these
                      parameters are also used for creation.

        Returns:
            tuple[EdgyEmbedTarget, bool]: A tuple containing the object and a boolean
                                          indicating whether the object was created (True)
                                          or retrieved (False).
        """
        ...

    @abstractmethod
    async def update_or_create(
        self, defaults: dict[str, Any] | Any | None = None, *args: Any, **kwargs: Any
    ) -> tuple[EdgyEmbedTarget, bool]:
        """
        Abstract method to update an object, or create it if it does not exist.

        Args:
            defaults (dict[str, Any] | Any | None): A dictionary of default values to use
                                                     when creating the object if it doesn't exist,
                                                     or values to update if it does.
            *args: Positional arguments for object creation if needed.
            **kwargs: Lookup parameters to find the object. If found, these
                      parameters are also used for updating. If not found,
                      these parameters are used for creation.

        Returns:
            tuple[EdgyEmbedTarget, bool]: A tuple containing the object and a boolean
                                          indicating whether the object was created (True)
                                          or updated (False).
        """
        ...

    update_or_insert = update_or_create

    @abstractmethod
    async def contains(self, instance: BaseModelType) -> bool:
        """
        Abstract method to check if the QuerySet contains a specific model instance.

        Args:
            instance (BaseModelType): The model instance to check for.

        Returns:
            bool: True if the QuerySet contains the instance, False otherwise.
        """
        ...

    like = contains

    @abstractmethod
    def transaction(self, *, force_rollback: bool = False, **kwargs: Any) -> Transaction:
        """
        Return database transaction for the assigned database.

        Args:
            force_rollback (bool): If True, forces the transaction to roll back regardless of success.
            **kwargs: Additional keyword arguments for the transaction.

        Returns:
            Transaction: A database transaction object.
        """

    @abstractmethod
    def using(
        self,
        *,
        database: str | Any | None | Database = Undefined,
        schema: str | Any | None | Literal[False] = Undefined,
    ) -> QuerySetType[EdgyModel, EdgyEmbedTarget]:
        """
        Abstract method to specify the database connection and/or schema to use for the QuerySet.

        Args:
            database (str | Any | None | Database): The database name or instance to use.
            schema (str | Any | None | Literal[False]): The schema name to use, or False to unset.

        Returns:
            QuerySetType: A new QuerySet instance configured with the specified database and/or schema.
        """
        ...

    @abstractmethod
    def extra_select(
        self,
        *extra: sqlalchemy.ClauseElement,
    ) -> QuerySetType[EdgyModel, EdgyEmbedTarget]:
        """
        Abstract method to add extra select clauses to the QuerySet.

        Args:
            *extra (sqlalchemy.ClauseElement): One or more SQLAlchemy clause elements
                                               to add to the SELECT statement.

        Returns:
            QuerySetType: A new QuerySet instance with the extra select clauses.
        """
        ...

    @abstractmethod
    def reference_select(
        self, references: reference_select_type
    ) -> QuerySetType[EdgyModel, EdgyEmbedTarget]:
        """
        Abstract method to select specific references (related fields) to be included in the results.

        Args:
            references (reference_select_type): A dictionary defining the references to select.

        Returns:
            QuerySetType: A new QuerySet instance with the specified references selected.
        """
        ...

    @abstractmethod
    def __await__(self) -> Generator[Any, None, list[EdgyEmbedTarget]]:
        """
        Abstract method to make the QuerySet awaitable, allowing direct `await` calls.

        When awaited, it typically executes the query and returns a list of results.

        Returns:
            Generator[Any, None, list[EdgyEmbedTarget]]: A generator that yields
                                                         control until the query completes,
                                                         then returns a list of `EdgyEmbedTarget` objects.
        """
        ...

    @abstractmethod
    def __aiter__(self) -> AsyncIterator[EdgyEmbedTarget]:
        """
        Abstract method to make the QuerySet asynchronously iterable.

        Allows iterating over query results using `async for`.

        Yields:
            AsyncIterator[EdgyEmbedTarget]: An asynchronous iterator that yields
                                            `EdgyEmbedTarget` objects one by one.
        """
        ...


QueryType = QuerySetType
"""
Type alias for QuerySetType, providing a shorthand for referencing the QuerySet interface.
"""
