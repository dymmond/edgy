from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable, Sequence
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Optional,
    Union,
)

if TYPE_CHECKING:
    import sqlalchemy
    from databasez.core.transaction import Transaction

    from edgy.core.connection.database import Database
    from edgy.core.db.models.base import BaseModel
    from edgy.core.db.models.managers import BaseManager
    from edgy.core.db.models.metaclasses import MetaInfo
    from edgy.core.db.querysets.base import QuerySet


class DescriptiveMeta:
    """
    The `Meta` class used to configure each metadata of the model.
    Abstract classes are not generated in the database, instead, they are simply used as
    a reference for field generation.

    Usage:

    .. code-block:: python3

        class User(Model):
            ...

            class Meta:
                registry = models
                tablename = "users"

    """

    ...  # pragma: no cover


class BaseModelType(ABC):
    """
    Type of edgy.Model and EdgyBaseModel
    """

    columns: ClassVar[sqlalchemy.sql.ColumnCollection]
    database: ClassVar[Database]
    table: ClassVar[sqlalchemy.Table]
    # Primary key columns
    pkcolumns: ClassVar[Sequence[str]]
    # Primary key fields
    pknames: ClassVar[Sequence[str]]
    query: ClassVar[BaseManager]
    query_related: ClassVar[BaseManager]
    meta: ClassVar[MetaInfo]
    Meta: ClassVar[DescriptiveMeta] = DescriptiveMeta()

    __parent__: ClassVar[Union[type[BaseModelType], None]] = None
    __is_proxy_model__: ClassVar[bool] = False
    __require_model_based_deletion__: ClassVar[bool] = False
    __reflected__: ClassVar[bool] = False
    _db_schemas: ClassVar[dict[str, type[BaseModelType]]]

    @property
    @abstractmethod
    def proxy_model(self) -> type[BaseModelType]: ...

    @property
    @abstractmethod
    def identifying_db_fields(self) -> Any:
        """The columns used for loading, can be set per instance defaults to pknames."""

    @property
    @abstractmethod
    def can_load(self) -> bool:
        """identifying_db_fields are completely specified."""

    @abstractmethod
    def transaction(self, *, force_rollback: bool = False, **kwargs: Any) -> Transaction:
        """Return database transaction for the assigned database."""

    @abstractmethod
    def get_columns_for_name(self, name: str) -> Sequence[sqlalchemy.Column]:
        """Helper for retrieving columns from field name."""

    @abstractmethod
    def identifying_clauses(self) -> Iterable[Any]:
        """Return clauses which are uniquely map to this object"""

    @classmethod
    @abstractmethod
    def generate_proxy_model(cls) -> type[BaseModel]:
        """
        Generates a proxy model for each model. This proxy model is a simple
        shallow copy of the original model being generated.
        """

    @abstractmethod
    async def load(self, only_needed: bool = False) -> None:
        """Load model"""

    @abstractmethod
    async def update(self, **kwargs: Any) -> Any:
        """
        Update operation of the database fields.
        """

    @abstractmethod
    async def save(
        self,
        force_insert: bool = False,
        values: Union[dict[str, Any], set[str], list[str], None] = None,
    ) -> BaseModelType:
        """Save model"""

    @abstractmethod
    async def delete(
        self, skip_post_delete_hooks: bool = False, remove_referenced_call: bool = False
    ) -> None:
        """Delete Model"""

    @abstractmethod
    async def load_recursive(
        self, only_needed: bool = True, only_needed_nest: bool = False
    ) -> None:
        """Load model and all models referenced by foreign keys."""

    @abstractmethod
    def model_dump(self, show_pk: Union[bool, None] = None, **kwargs: Any) -> dict[str, Any]:
        """
        An updated version of the model dump.
        It can show the pk always and handles the exclude attribute on fields correctly and
        contains the custom logic for fields with getters

        Extra Args:
            show_pk: bool - Enforces showing the primary key in the model_dump.
        """

    @classmethod
    @abstractmethod
    def build(
        cls, schema: Optional[str] = None, metadata: Optional[sqlalchemy.MetaData] = None
    ) -> sqlalchemy.Table:
        """
        Builds the SQLAlchemy table representation from the loaded fields.
        """

    @abstractmethod
    async def execute_post_save_hooks(self, fields: Sequence[str], force_insert: bool) -> None: ...

    @abstractmethod
    async def execute_pre_save_hooks(
        self, values: dict[str, Any], original: dict[str, Any], force_insert: bool
    ) -> dict[str, Any]:
        """
        For async operations after clean. Can be used to reintroduce stripped values for save.
        The async operations run in a transaction with save or update. This allows to intervene with the operation.
        Has also access to the defaults and can transform them.

        Returns: column values for saving.
        """

    @classmethod
    @abstractmethod
    def extract_column_values(
        cls,
        extracted_values: dict[str, Any],
        is_update: bool = False,
        is_partial: bool = False,
        instance: Optional[Union[BaseModelType, QuerySet]] = None,
        model_instance: Optional[BaseModelType] = None,
    ) -> dict[str, Any]:
        """
        Extracts all the default values from the given fields and returns the raw
        value corresponding to each field.
        """

    # helpers

    def extract_db_fields(self, only: Optional[Sequence[str]] = None) -> dict[str, Any]:
        """
        Extracts all the db fields, model references and fields.
        Related fields are not included because they are disjoint.
        """
        fields = self.meta.fields
        columns = self.table.columns

        if only is not None:
            return {k: v for k, v in self.__dict__.items() if k in only}

        return {k: v for k, v in self.__dict__.items() if k in fields or hasattr(columns, k)}

    def get_instance_name(self) -> str:
        """
        Returns the name of the class in lowercase.
        """
        return self.__class__.__name__.lower()

    def create_model_key(self) -> tuple:
        """
        Build a cache key for the model.
        """
        pk_key_list: list[Any] = [type(self).__name__]
        # there are no columns, only column results
        for attr in self.pkcolumns:
            pk_key_list.append(str(getattr(self, attr)))
        return tuple(pk_key_list)
