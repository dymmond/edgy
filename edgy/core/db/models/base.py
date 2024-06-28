import copy
from functools import cached_property
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Dict,
    Iterable,
    List,
    Literal,
    Optional,
    Sequence,
    Set,
    Type,
    Union,
    cast,
)

import sqlalchemy
from pydantic import BaseModel, ConfigDict
from pydantic_core._pydantic_core import SchemaValidator as SchemaValidator
from sqlalchemy.ext.asyncio import AsyncConnection
from typing_extensions import Self

from edgy.core.db.datastructures import Index, UniqueConstraint
from edgy.core.db.models._internal import DescriptiveMeta
from edgy.core.db.models.managers import Manager, RedirectManager
from edgy.core.db.models.metaclasses import BaseModelMeta, MetaInfo
from edgy.core.db.models.model_proxy import ProxyModel
from edgy.core.db.models.utils import build_pkcolumns, build_pknames
from edgy.core.utils.functional import edgy_setattr
from edgy.core.utils.models import DateParser, ModelParser, generify_model_fields
from edgy.core.utils.sync import run_sync
from edgy.exceptions import ImproperlyConfigured

if TYPE_CHECKING:
    from edgy import Model, Registry
    from edgy.core.db.fields.base import BaseField
    from edgy.core.signals import Broadcaster

_empty = cast(Set[str], frozenset())


class EdgyBaseModel(BaseModel, DateParser, ModelParser, metaclass=BaseModelMeta):
    """
    Base of all Edgy models with the core setup.
    """

    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)
    parent: ClassVar[Union[Type[Self], None]]
    is_proxy_model: ClassVar[bool] = False

    query: ClassVar[Manager] = Manager()
    query_related: ClassVar[RedirectManager] = RedirectManager(redirect_name="query")
    meta: ClassVar[MetaInfo] = MetaInfo(None, abstract=True)
    Meta: ClassVar[DescriptiveMeta] = DescriptiveMeta()
    __proxy_model__: ClassVar[Union[Type["Model"], None]] = None
    __db_model__: ClassVar[bool] = False
    __reflected__: ClassVar[bool] = False
    __raw_query__: ClassVar[Optional[str]] = None
    __using_schema__: ClassVar[Union[str, None]] = None
    __show_pk__: ClassVar[bool] = False

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        __show_pk__ = kwargs.pop("__show_pk__", False)
        kwargs = self.transform_input(kwargs, phase="creation")
        super().__init__(**kwargs)
        self.__dict__ = self.setup_model_from_kwargs(kwargs)
        self.__show_pk__ = __show_pk__

    @classmethod
    def transform_input(cls, kwargs: Any, phase: str) -> Any:
        """
        Expand to_model.
        """
        kwargs = {**kwargs}
        new_kwargs: Dict[str, Any] = {}

        fields = cls.meta.fields_mapping
        # phase 1: transform
        for field_name in cls.meta.input_modifying_fields:
            fields[field_name].modify_input(field_name, kwargs)
        # phase 2: apply to_model
        for key, value in kwargs.items():
            field = fields.get(key, None)
            if field is not None:
                new_kwargs.update(**field.to_model(key, value, phase=phase))
            else:
                new_kwargs[key] = value
        return new_kwargs

    def setup_model_from_kwargs(self, kwargs: Any) -> Any:
        """
        Loops and setup the kwargs of the model
        """

        return {
            k: v for k, v in kwargs.items() if k in self.meta.fields_mapping or k in self.meta.model_references
        }

    @property
    def raw_query(self) -> Any:
        return getattr(self, self.__raw_query__)

    @raw_query.setter
    def raw_query(self, value: Any) -> Any:
        edgy_setattr(self, self.raw_query, value)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self}>"

    def __str__(self) -> str:
        pkl = []
        for pkname in self.pknames:
            pkl.append(f"{pkname}={getattr(self, pkname, None)}")
        return f"{self.__class__.__name__}({', '.join(pkl)})"

    @cached_property
    def proxy_model(self) -> Any:
        return self.__class__.proxy_model

    @cached_property
    def identifying_db_fields(self) -> Any:
        """The columns used for loading, can be set per instance defaults to pknames"""
        return self.pkcolumns

    @property
    def can_load(self) -> bool:
        for field in self.identifying_db_fields:
            if self.__dict__.get(field) is None:
                return False
        return True

    @cached_property
    def signals(self) -> "Broadcaster":
        return self.__class__.signals  # type: ignore

    @property
    def table(self) -> sqlalchemy.Table:
        if getattr(self, "_table", None) is None:
            return cast("sqlalchemy.Table", self.__class__.table)
        return self._table

    @table.setter
    def table(self, value: sqlalchemy.Table) -> None:
        try:
            del self._pknames
        except AttributeError:
            pass
        try:
            del self._pkcolumns
        except AttributeError:
            pass
        self._table = value

    @property
    def pkcolumns(self) -> Sequence[str]:
        if self.__dict__.get("_pkcolumns", None) is None:
            if self.__dict__.get("_table", None) is None:
                self._pkcolumns: Sequence[str] = cast(Sequence[str], self.__class__.pkcolumns)
            else:
                build_pkcolumns(self)
        return self._pkcolumns

    @property
    def pknames(self) -> Sequence[str]:
        if self.__dict__.get("_pknames", None) is None:
            if self.__dict__.get("_table", None) is None:
                self._pknames: Sequence[str] = cast(Sequence[str], self.__class__.pknames)
            else:
                build_pknames(self)
        return self._pknames

    def get_columns_for_name(self, name: str) -> Sequence["sqlalchemy.Column"]:
        table = self.table
        meta = self.meta
        if name in meta.field_to_columns:
            return meta.field_to_columns[name]
        elif name in table.columns:
            return (table.columns[name],)
        else:
            return cast(Sequence["sqlalchemy.Column"], _empty)

    def identifying_clauses(self) -> Iterable[Any]:
        for field_name in self.identifying_db_fields:
            field = self.meta.fields_mapping.get(field_name)
            if field is not None:
                for column, value in field.clean(field_name, self.__dict__[field_name]).items():
                    yield getattr(self.table.columns, column) == value
            else:
                yield getattr(self.table.columns, field_name) == self.__dict__[field_name]

    @classmethod
    def generate_proxy_model(cls) -> Type["Model"]:
        """
        Generates a proxy model for each model. This proxy model is a simple
        shallow copy of the original model being generated.
        """
        if cls.__proxy_model__:
            return cls.__proxy_model__

        fields = {key: copy.copy(field) for key, field in cls.meta.fields_mapping.items()}
        proxy_model = ProxyModel(
            name=cls.__name__,
            module=cls.__module__,
            metadata=cls.meta,
            definitions=fields,
        )

        proxy_model.build()
        generify_model_fields(proxy_model.model)
        return proxy_model.model

    def model_dump(self, show_pk: Union[bool, None] = None, **kwargs: Any) -> Dict[str, Any]:
        """
        An updated version of the model dump.
        It can show the pk always and handles the exclude attribute on fields correctly and
        contains the custom logic for fields with getters

        Extra Args:
            show_pk: bool - Enforces showing the primary key in the model_dump.
        """
        # we want a copy
        exclude: Union[Set[str], Dict[str, Any], None] = kwargs.pop("exclude", None)
        if exclude is None:
            initial_full_field_exclude = _empty
            # must be writable
            exclude = set()
        elif isinstance(exclude, dict):
            initial_full_field_exclude = {k for k, v in exclude.items() if v is True}
            exclude = copy.copy(exclude)
        else:
            initial_full_field_exclude = set(exclude)
            exclude = copy.copy(initial_full_field_exclude)

        if isinstance(exclude, dict):
            exclude["__show_pk__"] = True
            for field_name in self.meta.excluded_fields:
                exclude[field_name] = True
        else:
            exclude.update(self.meta.special_getter_fields)
            exclude.update(self.meta.excluded_fields)
            exclude.add("__show_pk__")
        include: Union[Set[str], Dict[str, Any], None] = kwargs.pop("include", None)
        mode: Union[Literal["json", "python"], str] = kwargs.pop("mode", "python")

        should_show_pk = show_pk or self.__show_pk__
        model = dict(super().model_dump(exclude=exclude, include=include, mode=mode, **kwargs))
        # Workaround for metafields, computed field logic introduces many problems
        # so reimplement the logic here
        for field_name in self.meta.special_getter_fields:
            if field_name == "pk":
                continue
            if not should_show_pk or field_name not in self.pknames:
                if field_name in initial_full_field_exclude:
                    continue
                if include is not None and field_name not in include:
                    continue
                if getattr(field_name, "exclude", False):
                    continue
            field: BaseField = self.meta.fields_mapping[field_name]
            try:
                retval = field.__get__(self, self.__class__)
            except AttributeError:
                continue
            sub_include = None
            if isinstance(include, dict):
                sub_include = include.get(field_name, None)
                if sub_include is True:
                    sub_include = None
            sub_exclude = None
            if isinstance(exclude, dict):
                sub_exclude = exclude.get(field_name, None)
                if sub_exclude is True:
                    sub_exclude = None
            if isinstance(retval, BaseModel):
                retval = retval.model_dump(include=sub_include, exclude=sub_exclude, mode=mode, **kwargs)
            else:
                assert (
                    sub_include is None
                ), "sub include filters for CompositeField specified, but no Pydantic model is set"
                assert (
                    sub_exclude is None
                ), "sub exclude filters for CompositeField specified, but no Pydantic model is set"
                if mode == "json" and not getattr(field, "unsafe_json_serialization", False):
                    # skip field if it isn't a BaseModel and the mode is json and unsafe_json_serialization is not set
                    # currently unsafe_json_serialization exists only on ConcreteCompositeFields
                    continue
            alias: str = field_name
            if getattr(field, "serialization_alias", None):
                alias = cast(str, field.serialization_alias)
            elif getattr(field, "alias", None):
                alias = field.alias
            model[alias] = retval
        # tenants cause excluded fields to reappear
        # TODO: find a better bugfix
        for excluded_field in self.meta.excluded_fields:
            model.pop(excluded_field, None)
        return model

    @classmethod
    def build(cls, schema: Optional[str] = None) -> sqlalchemy.Table:
        """
        Builds the SQLAlchemy table representation from the loaded fields.
        """
        tablename: str = cls.meta.tablename  # type: ignore
        registry = cls.meta.registry
        assert registry is not None, "registry is not set"
        metadata: sqlalchemy.MetaData = cast("sqlalchemy.MetaData", registry._metadata)  # type: ignore
        metadata.schema = schema or registry.db_schema

        unique_together = cls.meta.unique_together
        index_constraints = cls.meta.indexes

        columns: List["sqlalchemy.Column"] = []
        global_constraints: List[Any] = []
        for name, field in cls.meta.fields_mapping.items():
            current_columns = field.get_columns(name)
            columns.extend(current_columns)
            global_constraints.extend(field.get_global_constraints(name, current_columns))

        # Handle the uniqueness together
        uniques = []
        for field in unique_together or []:
            unique_constraint = cls._get_unique_constraints(field)
            uniques.append(unique_constraint)

        # Handle the indexes
        indexes = []
        for field in index_constraints or []:
            index = cls._get_indexes(field)
            indexes.append(index)
        return sqlalchemy.Table(
            tablename,
            metadata,
            *columns,
            *uniques,
            *indexes,
            *global_constraints,
            extend_existing=True,
        )

    @classmethod
    def _get_unique_constraints(
        cls, columns: Union[Sequence, str, sqlalchemy.UniqueConstraint]
    ) -> Optional[sqlalchemy.UniqueConstraint]:
        """
        Returns the unique constraints for the model.

        The columns must be a a list, tuple of strings or a UniqueConstraint object.

        :return: Model UniqueConstraint.
        """
        if isinstance(columns, str):
            return sqlalchemy.UniqueConstraint(columns)
        elif isinstance(columns, UniqueConstraint):
            return sqlalchemy.UniqueConstraint(*columns.fields, name=columns.name)
        return sqlalchemy.UniqueConstraint(*columns)

    @classmethod
    def _get_indexes(cls, index: Index) -> Optional[sqlalchemy.Index]:
        """
        Creates the index based on the Index fields
        """
        return sqlalchemy.Index(index.name, *index.fields)  # type: ignore

    def extract_db_fields(self) -> Dict[str, Any]:
        """
        Extracts all the db fields, model references and fields.
        Related fields are not included because they are disjoint.
        """
        fields_mapping = self.meta.fields_mapping
        model_references = self.meta.model_references
        columns = self.__class__.columns
        return {k: v for k, v in self.__dict__.items() if k in fields_mapping or k in columns or k in model_references}

    def get_instance_name(self) -> str:
        """
        Returns the name of the class in lowercase.
        """
        return self.__class__.__name__.lower()

    async def load(self) -> None:
        raise NotImplementedError()

    def __setattr__(self, key: str, value: Any) -> None:
        fields_mapping = self.meta.fields_mapping
        field = fields_mapping.get(key, None)
        if field is not None:
            if hasattr(field, "__set__"):
                # not recommended, better to use to_model instead
                # used in related_fields to mask and not to implement to_model
                field.__set__(self, value)
            else:
                for k, v in field.to_model(key, value, phase="set").items():
                    # bypass __settr__
                    edgy_setattr(self, k, v)
        else:
            # bypass __settr__
            edgy_setattr(self, key, value)

    def __getattr__(self, name: str) -> Any:
        """
        Does following things
        1. Initialize managers on access
        2. Redirects get accesses to getter fields
        3. Run an one off query to populate any foreign key making sure
           it runs only once per foreign key avoiding multiple database calls.
        """
        manager = self.meta.managers.get(name)
        if manager is not None:
            if name not in self.__dict__:
                manager = copy.copy(manager)
                manager.instance = self
                self.__dict__[name] = manager
            return self.__dict__[name]

        field = self.meta.fields_mapping.get(name)
        if field is not None and hasattr(field, "__get__"):
            # no need to set an descriptor object
            return field.__get__(self, self.__class__)
        if name not in self.__dict__ and field is not None and name not in self.identifying_db_fields and self.can_load:
            run_sync(self.load())
            return self.__dict__[name]
        return super().__getattr__(name)

    def __eq__(self, other: Any) -> bool:
        # if self.__class__ != other.__class__:
        #     return False
        # somehow meta gets regenerated, so just compare tablename and registry.
        if self.meta.registry is not other.meta.registry:
            return False
        if self.meta.tablename != other.meta.tablename:
            return False
        self_dict = self._extract_values_from_field(self.extract_db_fields(), is_partial=True)
        other_dict = self._extract_values_from_field(other.extract_db_fields(), is_partial=True)
        key_set = {*self_dict.keys(), *other_dict.keys()}
        for field_name in key_set:
            if self_dict.get(field_name) != other_dict.get(field_name):
                return False
        return True


class EdgyBaseReflectModel(EdgyBaseModel):
    """
    Reflect on async engines is not yet supported, therefore, we need to make a sync_engine
    call.
    """

    __reflected__: ClassVar[bool] = True

    class Meta:
        abstract = True

    @classmethod
    def build(cls, schema: Optional[str] = None) -> Any:
        """
        The inspect is done in an async manner and reflects the objects from the database.
        """
        registry = cls.meta.registry
        assert registry is not None, "registry is not set"
        metadata: sqlalchemy.MetaData = registry._metadata
        schema_name = schema or registry.db_schema
        metadata.schema = schema_name

        tablename: str = cast("str", cls.meta.tablename)
        return run_sync(cls.reflect(registry, tablename, metadata, schema_name))

    @classmethod
    async def reflect(
        cls,
        registry: "Registry",
        tablename: str,
        metadata: sqlalchemy.MetaData,
        schema: Union[str, None] = None,
    ) -> sqlalchemy.Table:
        """
        Reflect a table from the database and return its SQLAlchemy Table object.

        This method connects to the database using the provided registry, reflects
        the table with the given name and metadata, and returns the SQLAlchemy
        Table object.

        Parameters:
            registry (Registry): The registry object containing the database engine.
            tablename (str): The name of the table to reflect.
            metadata (sqlalchemy.MetaData): The SQLAlchemy MetaData object to associate with the reflected table.
            schema (Union[str, None], optional): The schema name where the table is located. Defaults to None.

        Returns:
            sqlalchemy.Table: The reflected SQLAlchemy Table object.

        Raises:
            ImproperlyConfigured: If there is an error during the reflection process.
        """

        def execute_reflection(connection: AsyncConnection) -> sqlalchemy.Table:
            """Helper function to create and reflect the table."""
            try:
                return sqlalchemy.Table(tablename, metadata, schema=schema, autoload_with=connection)
            except Exception as e:
                raise e

        try:
            async with registry.engine.begin() as connection:
                table = await connection.run_sync(execute_reflection)
            await registry.engine.dispose()
            return table
        except Exception as e:
            raise ImproperlyConfigured(detail=str(e)) from e
