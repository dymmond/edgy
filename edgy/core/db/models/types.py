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
    transaction: ClassVar[TransactionCallProtocol]

    __parent__: ClassVar[type[BaseModelType] | None] = None
    __is_proxy_model__: ClassVar[bool] = False
    __require_model_based_deletion__: ClassVar[bool] = False
    __reflected__: ClassVar[bool] = False

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
    def get_columns_for_name(self, name: str) -> Sequence[sqlalchemy.Column]:
        """Helper for retrieving columns from field name."""

    @abstractmethod
    def identifying_clauses(self) -> Iterable[Any]:
        """Return clauses which are uniquely map to this object"""

    @classmethod
    @abstractmethod
    def generate_proxy_model(cls) -> type[Model]:
        """
        Generates a proxy model for each model. This proxy model is a simple
        shallow copy of the original model being generated.
        """

    @abstractmethod
    async def load(self, only_needed: bool = False) -> None:
        """Load model"""

    @abstractmethod
    async def update(self, **kwargs: Any) -> BaseModelType:
        """
        Update operation of the database fields.
        """

    @abstractmethod
    async def real_save(
        self,
        force_insert: bool = False,
        values: dict[str, Any] | set[str] | list[str] | None = None,
    ) -> BaseModelType:
        """Save model. For customizations used by querysets and direct calls."""

    @abstractmethod
    async def save(
        self,
        force_insert: bool = False,
        values: dict[str, Any] | set[str] | list[str] | None = None,
    ) -> BaseModelType:
        """Save model. For customizations only by direct calls."""

    @abstractmethod
    async def raw_delete(
        self, *, skip_post_delete_hooks: bool, remove_referenced_call: bool | str
    ) -> None:
        """
        Delete Model. Raw version called by QuerySet and delete.
        For customization. Should be called for user and non-user-facing customizations.

        Kwargs:
            skip_post_delete_hooks: Skip field post deletehooks.
            remove_referenced_call: Either bool if the originator of the call is the model itself or
                                    string from which field the delete call originates from
                                    Should be passed through by customizations.
        """
        # Why remove_referenced_call as string?
        # When traversing a RelatedField for deletions there are stub back references
        # If not trimmed, they are used for model deletion.

    @abstractmethod
    async def delete(self, skip_post_delete_hooks: bool = False) -> None:
        """Delete Model. User-facing, not used by internal methods."""

    @abstractmethod
    async def load_recursive(
        self, only_needed: bool = True, only_needed_nest: bool = False
    ) -> None:
        """Load model and all models referenced by foreign keys."""

    @abstractmethod
    def model_dump(self, show_pk: bool | None = None, **kwargs: Any) -> dict[str, Any]:
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
        cls,
        schema: str | None = None,
        metadata: sqlalchemy.MetaData | None = None,
    ) -> sqlalchemy.Table:
        """
        Builds the SQLAlchemy table representation from the loaded fields.
        """

    @abstractmethod
    async def execute_post_save_hooks(self, fields: Sequence[str], is_update: bool) -> None: ...

    @abstractmethod
    async def execute_pre_save_hooks(
        self, values: dict[str, Any], original: dict[str, Any], is_update: bool
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
        phase: str = "",
        instance: BaseModelType | QuerySet | None = None,
        model_instance: BaseModelType | None = None,
        evaluate_kwarg_values: bool = False,
    ) -> dict[str, Any]:
        """
        Extracts all the default values from the given fields and returns the raw
        value corresponding to each field.
        """

    # helpers
    @classmethod
    def get_real_class(cls) -> BaseModelType:
        return cls.__parent__ if cls.__is_proxy_model__ else cls  # type: ignore

    def extract_db_fields(self, only: Container[str] | None = None) -> dict[str, Any]:
        """
        Extracts all the db fields, model references and fields.
        Related fields are not included because they are disjoint.
        """
        fields = self.meta.fields
        columns = self.table.columns

        if only is not None:
            assert all(k in fields or hasattr(columns, k) for k in only), (
                f'"only" includes invalid fields, {only}'
            )
            return {k: v for k, v in self.__dict__.items() if k in only}

        return {k: v for k, v in self.__dict__.items() if k in fields or hasattr(columns, k)}

    def get_instance_name(self) -> str:
        """
        Returns the name of the class in lowercase.
        """
        return type(self).__name__.lower()

    def create_model_key(self) -> tuple:
        """
        Build a cache key for the model.
        """
        pk_key_list: list[Any] = [type(self).__name__]
        # there are no columns, only column results
        for attr in self.pkcolumns:
            pk_key_list.append(str(getattr(self, attr)))
        return tuple(pk_key_list)
