from abc import ABC, abstractmethod
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Dict,
    Iterable,
    List,
    Optional,
    Sequence,
    Type,
    Union,
)

if TYPE_CHECKING:
    import sqlalchemy

    from edgy import Database, Model
    from edgy.core.db.models.managers import BaseManager
    from edgy.core.db.models.metaclasses import MetaInfo


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
    Type of EdgyBaseModel
    """

    columns: ClassVar["sqlalchemy.sql.ColumnCollection"]
    database: ClassVar["Database"]
    query: ClassVar["BaseManager"]
    query_related: ClassVar["BaseManager"]
    meta: ClassVar["MetaInfo"]
    _db_schemas: ClassVar[Dict[str, Type["BaseModelType"]]]
    Meta: ClassVar[DescriptiveMeta] = DescriptiveMeta()

    __parent__: ClassVar[Union[Type["BaseModelType"], None]] = None
    __is_proxy_model__: ClassVar[bool] = False
    __require_model_based_deletion__: ClassVar[bool] = False
    __reflected__: ClassVar[bool] = False

    @property
    @abstractmethod
    def proxy_model(self) -> Any: ...

    @property
    @abstractmethod
    def identifying_db_fields(self) -> Any:
        """The columns used for loading, can be set per instance defaults to pknames."""

    @property
    @abstractmethod
    def can_load(self) -> bool:
        """identifying_db_fields are completely specified."""

    @property
    @abstractmethod
    def table(self) -> "sqlalchemy.Table":
        """Overwritable table attribute."""

    @property
    @abstractmethod
    def pkcolumns(self) -> Sequence[str]:
        """Primary key columns."""

    @property
    @abstractmethod
    def pknames(self) -> Sequence[str]:
        """Primary key fields."""

    @abstractmethod
    def get_columns_for_name(self, name: str) -> Sequence["sqlalchemy.Column"]:
        """Helper for retrieving columns from field name."""

    @abstractmethod
    def identifying_clauses(self) -> Iterable[Any]:
        """Return clauses which are uniquely map to this object"""

    @classmethod
    @abstractmethod
    def generate_proxy_model(cls) -> Type["Model"]:
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
        force_save: bool = False,
        values: Dict[str, Any] = None,
        **kwargs: Any,
    ) -> Union["Model", Any]:
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
    def model_dump(self, show_pk: Union[bool, None] = None, **kwargs: Any) -> Dict[str, Any]:
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
        cls, schema: Optional[str] = None, metadata: Optional["sqlalchemy.MetaData"] = None
    ) -> "sqlalchemy.Table":
        """
        Builds the SQLAlchemy table representation from the loaded fields.
        """

    @abstractmethod
    async def execute_post_save_hooks(self, fields: Sequence[str]) -> None: ...

    @abstractmethod
    async def execute_pre_save_hooks(
        self, values: Dict[str, Any], original: Dict[str, Any], force_insert: bool
    ) -> Dict[str, Any]:
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
        extracted_values: Dict[str, Any],
        is_update: bool = False,
        is_partial: bool = False,
    ) -> Dict[str, Any]:
        """
        Extracts all the default values from the given fields and returns the raw
        value corresponding to each field.
        """

    # helpers

    def extract_db_fields(self, only: Optional[Sequence[str]] = None) -> Dict[str, Any]:
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
        pk_key_list: List[Any] = [type(self).__name__]
        # there are no columns, only column results
        for attr in self.pkcolumns:
            pk_key_list.append(str(getattr(self, attr)))
        return tuple(pk_key_list)
