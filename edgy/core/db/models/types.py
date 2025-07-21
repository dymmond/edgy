from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Container, Iterable, Sequence
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    import sqlalchemy

    from edgy.core.connection.database import Database
    from edgy.core.db.models.managers import BaseManager
    from edgy.core.db.models.metaclasses import MetaInfo
    from edgy.core.db.models.model import Model
    from edgy.core.db.querysets.base import QuerySet
    from edgy.protocols.transaction_call import TransactionCallProtocol


class DescriptiveMeta:
    """
    The `Meta` class is used to configure various metadata options for an Edgy model.

    This inner class allows users to define model-specific settings such as
    the associated database registry, the table name in the database, and
    whether the model is abstract. Abstract models are not materialized as
    database tables but serve as base classes for other models, providing
    shared fields and configurations.

    Usage Example:

    ```python
    from edgy import Model, Registry, Database

    database = Database("sqlite:///db.sqlite")
    models = Registry(database=database)

    class User(Model):
        id: int = edgy.IntegerField(primary_key=True)
        name: str = edgy.CharField(max_length=100)

        class Meta:
            # Associate this model with a specific registry
            registry = models
            # Explicitly define the table name in the database
            tablename = "users"
    ```
    """

    ...  # pragma: no cover


class BaseModelType(ABC):
    """
    An abstract base class defining the common interface and required properties
    for all Edgy models (e.g., `edgy.Model` and `EdgyBaseModel`).

    This class ensures that all concrete model implementations adhere to a
    standard structure, providing essential attributes and abstract methods
    that must be implemented by subclasses. It defines core components like
    database connection, SQLAlchemy table representation, primary key information,
    and various CRUD operations.
    """

    # Class variables providing metadata and core components for the model.
    columns: ClassVar[sqlalchemy.sql.ColumnCollection]
    database: ClassVar[Database]
    table: ClassVar[sqlalchemy.Table]
    # `pkcolumns` stores the names of the primary key columns in the database table.
    pkcolumns: ClassVar[Sequence[str]]
    # `pknames` stores the names of the primary key fields in the model.
    pknames: ClassVar[Sequence[str]]
    # `query` is the default manager for performing database operations on the model.
    query: ClassVar[BaseManager]
    # `query_related` is a manager specifically for handling related queries.
    query_related: ClassVar[BaseManager]
    # `meta` holds an instance of `MetaInfo` containing model metadata.
    meta: ClassVar[MetaInfo]
    # `Meta` is a reference to the inner `DescriptiveMeta` class for configuration.
    Meta: ClassVar[DescriptiveMeta] = DescriptiveMeta()
    # `transaction` provides access to transaction-related functionalities.
    transaction: ClassVar[TransactionCallProtocol]

    # `__parent__` references the parent model in cases of inheritance or proxy models.
    __parent__: ClassVar[type[BaseModelType] | None] = None
    # `__is_proxy_model__` indicates if the current model is a proxy model.
    __is_proxy_model__: ClassVar[bool] = False
    # `__require_model_based_deletion__` indicates if deletion requires a model instance.
    __require_model_based_deletion__: ClassVar[bool] = False
    # `__reflected__` indicates if the model is reflected from an existing database table.
    __reflected__: ClassVar[bool] = False

    @property
    @abstractmethod
    def proxy_model(self) -> type[BaseModelType]:
        """
        Abstract property that returns a proxy model instance for the current model.

        This is typically a shallow copy used for specific internal operations
        without affecting the main model.

        Returns:
            type[BaseModelType]: A type representing the proxy model.
        """

    @property
    @abstractmethod
    def identifying_db_fields(self) -> Any:
        """
        Abstract property that returns the columns used for loading a model instance.

        By default, this will be the primary key names (`pknames`), but it can be
        overridden for specific instances if alternative fields are used for identification.

        Returns:
            Any: A representation of the identifying database fields.
        """

    @property
    @abstractmethod
    def can_load(self) -> bool:
        """
        Abstract property that indicates whether the model instance has enough
        identifying information to be loaded from the database.

        This is `True` if all `identifying_db_fields` are completely specified.

        Returns:
            bool: `True` if the model can be loaded; `False` otherwise.
        """

    @abstractmethod
    def get_columns_for_name(self, name: str) -> Sequence[sqlalchemy.Column]:
        """
        Abstract method to retrieve SQLAlchemy column objects associated with a
        given field name in the model.

        Args:
            name (str): The name of the field for which to retrieve columns.

        Returns:
            Sequence[sqlalchemy.Column]: A sequence of SQLAlchemy Column objects.
        """

    @abstractmethod
    def identifying_clauses(self) -> Iterable[Any]:
        """
        Abstract method that returns SQLAlchemy clauses that uniquely identify
        this model object in the database.

        These clauses are typically based on the primary key values of the instance.

        Returns:
            Iterable[Any]: An iterable of SQLAlchemy WHERE clauses.
        """

    @classmethod
    @abstractmethod
    def generate_proxy_model(cls) -> type[Model]:
        """
        Abstract class method to generate a proxy model for the current model class.

        A proxy model is a simple shallow copy of the original model, used for
        specific internal purposes without being added to the main model registry.

        Returns:
            type[Model]: A new model class representing the proxy model.
        """

    @abstractmethod
    async def load(self, only_needed: bool = False) -> None:
        """
        Abstract asynchronous method to load the model instance's data from the database.

        This method populates the model's attributes with data retrieved from the database
        based on its identifying fields.

        Args:
            only_needed (bool): If `True`, only loads fields that are not already present
                                or are explicitly marked as needed. Defaults to `False`.
        """

    @abstractmethod
    async def update(self, **kwargs: Any) -> BaseModelType:
        """
        Abstract asynchronous method to update the database record corresponding to
        the model instance with the provided keyword arguments.

        Args:
            **kwargs (Any): Keyword arguments representing the fields and their new values
                            to be updated in the database.

        Returns:
            BaseModelType: The updated model instance.
        """

    @abstractmethod
    async def real_save(
        self,
        force_insert: bool = False,
        values: dict[str, Any] | set[str] | list[str] | None = None,
    ) -> BaseModelType:
        """
        Abstract asynchronous method for saving the model instance to the database.

        This is the raw save operation used internally by querysets and direct calls.
        It allows for fine-grained control over the save process.

        Args:
            force_insert (bool): If `True`, forces an SQL INSERT operation, even if
                                 the instance might already exist (e.g., if primary key is set).
                                 Defaults to `False`.
            values (dict[str, Any] | set[str] | list[str] | None): Optional. A dictionary of
                                                                 values to save, or a set/list
                                                                 of field names to save.
                                                                 Defaults to `None`.

        Returns:
            BaseModelType: The saved model instance.
        """

    @abstractmethod
    async def save(
        self,
        force_insert: bool = False,
        values: dict[str, Any] | set[str] | list[str] | None = None,
    ) -> BaseModelType:
        """
        Abstract asynchronous method for saving the model instance to the database.

        This is the user-facing save operation, intended for direct calls on model instances.
        It provides a simpler interface compared to `real_save`.

        Args:
            force_insert (bool): If `True`, forces an SQL INSERT operation. Defaults to `False`.
            values (dict[str, Any] | set[str] | list[str] | None): Optional. Values or field names
                                                                 to save. Defaults to `None`.

        Returns:
            BaseModelType: The saved model instance.
        """

    @abstractmethod
    async def raw_delete(
        self, *, skip_post_delete_hooks: bool, remove_referenced_call: bool | str
    ) -> None:
        """
        Abstract asynchronous method to delete the model instance from the database.

        This is the raw deletion method, called internally by QuerySet and the public
        `delete` method. It is designed for internal customization and should be
        used for both user-facing and non-user-facing customizations.

        Args:
            skip_post_delete_hooks (bool): If `True`, skips the execution of post-delete
                                           hooks on related fields.
            remove_referenced_call (bool | str): Indicates whether the deletion call
                                                 originates from the model itself (`True`)
                                                 or from a specific field (`str`). This helps
                                                 in managing cascading deletions and preventing
                                                 infinite recursion in circular relationships.
                                                 Should be passed through by customizations.

        Notes:
            The `remove_referenced_call` as a string is crucial when traversing
            related fields for deletions, as it helps in trimming stub back
            references that might otherwise lead to incorrect model deletions.
        """

    @abstractmethod
    async def delete(self, skip_post_delete_hooks: bool = False) -> None:
        """
        Abstract asynchronous method to delete the model instance from the database.

        This is the user-facing delete operation, intended for direct calls on
        model instances and not typically used by internal methods which prefer `raw_delete`.

        Args:
            skip_post_delete_hooks (bool): If `True`, skips the execution of post-delete
                                           hooks on related fields. Defaults to `False`.
        """

    @abstractmethod
    async def load_recursive(
        self, only_needed: bool = True, only_needed_nest: bool = False
    ) -> None:
        """
        Abstract asynchronous method to load the model instance and all models
        referenced by its foreign keys recursively.

        This method ensures that related objects are also loaded into the model
        instance, providing a complete graph of interconnected data.

        Args:
            only_needed (bool): If `True`, only loads fields that are not already present
                                or are explicitly marked as needed for the current model.
                                Defaults to `True`.
            only_needed_nest (bool): If `True`, applies the `only_needed` logic
                                     recursively to nested (related) models.
                                     Defaults to `False`.
        """

    @abstractmethod
    def model_dump(self, show_pk: bool | None = None, **kwargs: Any) -> dict[str, Any]:
        """
        Abstract method that returns a dictionary representation of the model instance.

        This method enhances the standard `pydantic.BaseModel.model_dump` by providing
        additional control over primary key visibility and correctly handling
        field exclusions and custom getter logic.

        Args:
            show_pk (bool | None): If `True`, forces the inclusion of the primary key
                                   in the dumped dictionary, even if it's otherwise excluded.
                                   If `None`, follows the default exclusion rules.
                                   Defaults to `None`.
            **kwargs (Any): Additional keyword arguments to pass to the underlying
                            Pydantic `model_dump` method.

        Returns:
            dict[str, Any]: A dictionary containing the model's data.
        """

    @classmethod
    @abstractmethod
    def build(
        cls,
        schema: str | None = None,
        metadata: sqlalchemy.MetaData | None = None,
    ) -> sqlalchemy.Table:
        """
        Abstract class method to build and return the SQLAlchemy table representation
        for the model from its loaded fields.

        This method is responsible for translating the Edgy model definition into
        a SQLAlchemy `Table` object, which is then used for database schema generation
        and query execution.

        Args:
            schema (str | None): The database schema name to associate with the table.
                                 Defaults to `None`.
            metadata (sqlalchemy.MetaData | None): An optional SQLAlchemy `MetaData`
                                                   object to which the table should be
                                                   bound. Defaults to `None`.

        Returns:
            sqlalchemy.Table: The constructed SQLAlchemy Table object.
        """

    @abstractmethod
    async def execute_post_save_hooks(self, fields: Sequence[str], is_update: bool) -> None:
        """
        Abstract asynchronous method to execute post-save hooks for the model.

        These hooks are custom functions or methods that run after a model instance
        has been successfully saved (either inserted or updated) to the database.
        They can be used for side effects, logging, or triggering further operations.

        Args:
            fields (Sequence[str]): A sequence of field names that were affected during the save operation.
            is_update (bool): `True` if the save operation was an update; `False` if it was an insert.
        """
        ...

    @abstractmethod
    async def execute_pre_save_hooks(
        self, values: dict[str, Any], original: dict[str, Any], is_update: bool
    ) -> dict[str, Any]:
        """
        Abstract asynchronous method to execute pre-save hooks for the model.

        These hooks are custom functions or methods that run before a model instance
        is saved or updated in the database. They operate within the same transaction
        as the save/update operation, allowing for modification of values,
        validation, or other preparatory actions.

        Args:
            values (dict[str, Any]): A dictionary of the current values to be saved.
            original (dict[str, Any]): A dictionary of the original values before modification,
                                       useful in update scenarios.
            is_update (bool): `True` if the save operation is an update; `False` if it's an insert.

        Returns:
            dict[str, Any]: The potentially modified dictionary of column values that
                            will be used for saving. This allows for reintroducing
                            stripped values or transforming them.
        """

    @classmethod
    @abstractmethod
    def extract_column_values(
        cls,
        extracted_values: dict[str, Any],
        is_update: bool = False,
        is_partial: bool = False,
        phase: str = "",
        instance: BaseModelType | QuerySet | None = None,
        model_instance: BaseModelType | None = None,
        evaluate_kwarg_values: bool = False,
    ) -> dict[str, Any]:
        """
        Abstract class method to extract and process column values from a dictionary,
        including default values, for database operations.

        This method is crucial for preparing data before insertion or update. It
        handles the extraction of raw values corresponding to each field and
        can apply logic based on whether it's an update, a partial update, or
        a specific phase of data processing.

        Args:
            extracted_values (dict[str, Any]): A dictionary of values to be processed.
            is_update (bool): If `True`, indicates the operation is an update.
                              Defaults to `False`.
            is_partial (bool): If `True`, indicates a partial update where not all
                                fields are present. Defaults to `False`.
            phase (str): A string indicating the current phase of extraction,
                         e.g., "save", "create". Defaults to an empty string.
            instance (BaseModelType | QuerySet | None): The model instance or QuerySet
                                                         from which values are being extracted.
                                                         Defaults to `None`.
            model_instance (BaseModelType | None): The specific model instance being operated on.
                                                  Defaults to `None`.
            evaluate_kwarg_values (bool): If `True`, evaluates values that are
                                         callable (e.g., default factories).
                                         Defaults to `False`.

        Returns:
            dict[str, Any]: A dictionary containing the extracted and processed column values.
        """

    # helper methods

    @classmethod
    def get_real_class(cls) -> type[BaseModelType]:
        """
        Returns the concrete (non-proxy) class of the model instance.

        If the current instance is a proxy model, it returns its parent (the original
        model class). Otherwise, it returns the class itself.

        Returns:
            type[BaseModelType]: The real, non-proxy class of the model.
        """
        # Return the parent class if this is a proxy model, otherwise return the class itself.
        return cls.__parent__ if cls.__is_proxy_model__ else cls

    def extract_db_fields(self, only: Container[str] | None = None) -> dict[str, Any]:
        """
        Extracts and returns a dictionary of database-related fields from the model instance.

        This includes direct model fields and SQLAlchemy column attributes, but excludes
        related fields which are handled separately due to their disjoint nature.

        Args:
            only (Container[str] | None): An optional container of field names to include
                                          in the extraction. If `None`, all relevant fields
                                          are extracted. Defaults to `None`.

        Returns:
            dict[str, Any]: A dictionary where keys are field names and values are their
                            corresponding database values.

        Raises:
            AssertionError: If `only` contains field names that do not exist in the model's
                            fields or as SQLAlchemy columns.
        """
        # Get all defined fields from the model's meta information.
        fields = self.meta.fields
        # Get the SQLAlchemy columns associated with the model's table.
        columns = self.table.columns

        # If `only` is specified, filter the dictionary to include only the specified keys.
        # An assertion ensures that all keys in `only` are valid fields or column attributes.
        if only is not None:
            assert all(k in fields or hasattr(columns, k) for k in only), (
                f'"only" includes invalid fields, {only}'
            )
            return {k: v for k, v in self.__dict__.items() if k in only}

        # If `only` is not specified, return all attributes that are either model fields
        # or SQLAlchemy column attributes.
        return {k: v for k, v in self.__dict__.items() if k in fields or hasattr(columns, k)}

    def get_instance_name(self) -> str:
        """
        Returns the lowercase name of the model's class.

        This is typically used for generating default table names or for
        identification purposes.

        Returns:
            str: The lowercase name of the model's class.
        """
        return type(self).__name__.lower()

    def create_model_key(self) -> tuple:
        """
        Generates a unique cache key for the model instance.

        The key is composed of the model's class name and the string representation
        of its primary key column values. This key can be used for caching model
        instances to improve performance.

        Returns:
            tuple: A tuple representing the unique cache key for the model instance.
        """
        # Start the key with the model's class name.
        pk_key_list: list[Any] = [type(self).__name__]
        # Iterate over primary key column names and append their string values to the key list.
        # Note: `pkcolumns` contains column names, not column objects.
        for attr in self.pkcolumns:
            pk_key_list.append(str(getattr(self, attr)))
        # Convert the list to a tuple to make it hashable for use as a dictionary key.
        return tuple(pk_key_list)
