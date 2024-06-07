import copy
from functools import cached_property
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Dict,
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
from edgy.core.db.models.managers import Manager
from edgy.core.db.models.metaclasses import BaseModelMeta, MetaInfo
from edgy.core.db.models.model_proxy import ProxyModel
from edgy.core.utils.functional import edgy_setattr
from edgy.core.utils.models import DateParser, ModelParser, generify_model_fields
from edgy.core.utils.sync import run_sync
from edgy.exceptions import ImproperlyConfigured

if TYPE_CHECKING:
    from edgy import Model, Registry
    from edgy.core.signals import Broadcaster

EXCLUDED_LOOKUP = ["__model_references__", "_table"]

_empty = cast(Set[str], frozenset())


class EdgyBaseModel(BaseModel, DateParser, ModelParser, metaclass=BaseModelMeta):
    """
    Base of all Edgy models with the core setup.
    """

    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)
    parent: ClassVar[Union[Type[Self], None]]
    is_proxy_model: ClassVar[bool] = False

    query: ClassVar[Manager] = Manager()
    meta: ClassVar[MetaInfo] = MetaInfo(None)
    Meta: ClassVar[DescriptiveMeta] = DescriptiveMeta()
    __proxy_model__: ClassVar[Union[Type["Model"], None]] = None
    __db_model__: ClassVar[bool] = False
    __reflected__: ClassVar[bool] = False
    __raw_query__: ClassVar[Optional[str]] = None
    __using_schema__: ClassVar[Union[str, None]] = None
    __model_references__: ClassVar[Any] = None
    __show_pk__: ClassVar[bool] = False

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.__show_pk__ = kwargs.pop("__show_pk__", False)
        kwargs = self.transform_input(kwargs, phase="creation")
        super().__init__(**kwargs)
        model_references = self.setup_model_references_from_kwargs(kwargs)
        values = self.setup_model_fields_from_kwargs(kwargs)
        self.__dict__ = values
        self.__model_references__ = model_references

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

    def setup_model_references_from_kwargs(self, kwargs: Any) -> Any:
        """
        Loops and setup the kwargs of the model
        """
        model_references = {k: v for k, v in kwargs.items() if k in self.meta.model_references}
        return model_references

    def setup_model_fields_from_kwargs(self, kwargs: Any) -> Any:
        """
        Loops and setup the kwargs of the model
        """

        kwargs = {
            k: v for k, v in kwargs.items() if k in self.meta.fields_mapping and k not in self.meta.model_references
        }

        for key, value in kwargs.items():
            field = self.meta.fields_mapping.get(key, None)
            if not field:
                if not hasattr(self, key):
                    raise ValueError(f"Invalid keyword {key} for class {self.__class__.__name__}")

            # Add to the kwargs dict
            kwargs[key] = value
        return kwargs

    @property
    def raw_query(self) -> Any:
        return getattr(self, self.__raw_query__)

    @raw_query.setter
    def raw_query(self, value: Any) -> Any:
        edgy_setattr(self, self.raw_query, value)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self}>"

    def __str__(self) -> str:
        pknames = self.meta.pk_attributes
        pkl = []
        for pkname in pknames:
            pkl.append(f"{pkname}={getattr(self, pkname, None)}")
        return f"{self.__class__.__name__}({', '.join(pkl)})"

    @cached_property
    def proxy_model(self) -> Any:
        return self.__class__.proxy_model

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
        self._table = value

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

    @cached_property
    def special_getter_fields(self) -> Set[str]:
        """
        Pydantic computed fields can't be used as field yet.
        This reimplements the pydantic logic for fields with __get__ method
        """
        return cast(
            Set[str],
            frozenset(key for key, field in self.meta.fields_mapping.items() if hasattr(field, "__get__")),
        )

    @cached_property
    def excluded_fields(self) -> Set[str]:
        """
        Pydantic should exclude fields with exclude flag set, but it doesn't
        so work around here
        """
        # should be handled by pydantic but isn't so workaround
        return cast(
            Set[str],
            frozenset(key for key, field in self.meta.fields_mapping.items() if getattr(field, "exclude", False)),
        )

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
            for field in self.excluded_fields:
                exclude[field] = True
        else:
            exclude.update(self.special_getter_fields)
            exclude.update(self.excluded_fields)
            exclude.add("__show_pk__")
        include: Union[Set[str], Dict[str, Any], None] = kwargs.pop("include", None)
        mode: Union[Literal["json", "python"], str] = kwargs.pop("mode", "python")

        should_show_pk = show_pk or self.__show_pk__
        model = dict(super().model_dump(exclude=exclude, include=include, mode=mode, **kwargs))
        # Workaround for metafields, computed field logic introduces many problems
        # so reimplement the logic here
        for field_name in self.special_getter_fields:
            if field_name == "pk":
                continue
            if not should_show_pk or field_name not in self.pknames:
                if field_name in initial_full_field_exclude:
                    continue
                if include is not None and field_name not in include:
                    continue
                if getattr(field_name, "exclude", False):
                    continue
            field = self.fields[field_name]
            retval = field.__get__(self, self.__class__)
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
            alias = field_name
            if getattr(field, "serialization_alias", None):
                alias = field.serialization_alias
            elif getattr(field, "alias", None):
                alias = field.alias
            model[alias] = retval
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

        columns = []
        global_constraints = []
        for name, field in cls.fields.items():
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

    def update_from_dict(self, dict_values: Dict[str, Any]) -> Self:
        """Updates the current model object with the new fields and possible model_references"""
        for key, value in dict_values.items():
            setattr(self, key, value)
        return self

    def extract_db_model_references(self) -> Dict[str, Any]:
        """
        Extracts all the model references (ModelRef) from the model
        """
        related_fields = self.meta.related_fields
        return {k: v for k, v in self.__model_references__.items() if k not in related_fields}

    def extract_db_fields(self) -> Dict[str, Any]:
        """
        Extacts all the db fields and excludes the related_fields since those
        are simply relations.
        """
        related_fields = self.meta.related_fields
        return {k: v for k, v in self.__dict__.items() if k not in related_fields and k not in EXCLUDED_LOOKUP}

    def get_instance_name(self) -> str:
        """
        Returns the name of the class in lowercase.
        """
        return self.__class__.__name__.lower()

    def __setattr__(self, key: str, value: Any) -> None:
        field = self.meta.fields_mapping.get(key, None)
        if field is not None:
            if hasattr(field, "__set__"):
                # not recommended, better to use to_model instead
                # used in related_fields to mask and not to implement to_model
                field.__set__(self, value)
            else:
                for k, v in field.to_model(key, value, phase="set").items():
                    edgy_setattr(self, k, v)
        else:
            edgy_setattr(self, key, value)

    def __get_instance_values(self, instance: Any) -> Set[Any]:
        fields = self.meta.fields_mapping
        return {v for k, v in instance.__dict__.items() if k in fields and v is not None}

    def __eq__(self, other: Any) -> bool:
        if self.__class__ != other.__class__:
            return False

        original = self.__get_instance_values(instance=self)
        other_values = self.__get_instance_values(instance=other)
        if original != other_values:
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
