import contextlib
import copy
import warnings
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

from edgy.core.db.datastructures import Index, UniqueConstraint
from edgy.core.db.models.managers import Manager, RedirectManager
from edgy.core.db.models.metaclasses import BaseModelMeta, MetaInfo
from edgy.core.db.models.mixins import ModelParser
from edgy.core.db.models.model_proxy import ProxyModel
from edgy.core.db.models.utils import build_pkcolumns, build_pknames
from edgy.core.utils.functional import edgy_setattr
from edgy.core.utils.models import generify_model_fields
from edgy.core.utils.sync import run_sync

from .types import BaseModelType

if TYPE_CHECKING:
    from edgy import Model
    from edgy.core.db.fields.types import BaseFieldType
    from edgy.core.signals import Broadcaster

_empty = cast(Set[str], frozenset())


class EdgyBaseModel(ModelParser, BaseModel, BaseModelType, metaclass=BaseModelMeta):
    """
    Base of all Edgy models with the core setup.
    """

    model_config = ConfigDict(extra="ignore", arbitrary_types_allowed=True)

    query: ClassVar[Manager] = Manager()
    query_related: ClassVar[RedirectManager] = RedirectManager(redirect_name="query")
    meta: ClassVar[MetaInfo] = MetaInfo(None, abstract=True)
    __proxy_model__: ClassVar[Union[Type["Model"], None]] = None
    __db_model__: ClassVar[bool] = False
    __reflected__: ClassVar[bool] = False
    __using_schema__: ClassVar[Union[str, None]] = None
    __show_pk__: ClassVar[bool] = False
    # private attribute
    _loaded_or_deleted: bool = False
    _return_load_coro_on_attr_access: bool = False

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        __show_pk__ = kwargs.pop("__show_pk__", False)
        kwargs = self.transform_input(kwargs, phase="creation")
        super().__init__(**kwargs)
        self.__dict__ = self.setup_model_from_kwargs(kwargs)
        self.__show_pk__ = __show_pk__
        # always set them in __dict__ to prevent __getattr__ loop
        self._loaded_or_deleted = False
        self._return_load_coro_on_attr_access: bool = False

    @classmethod
    def transform_input(cls, kwargs: Any, phase: str) -> Any:
        """
        Expand to_model.
        """
        kwargs = {**kwargs}
        new_kwargs: Dict[str, Any] = {}

        fields = cls.meta.fields
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
            k: v
            for k, v in kwargs.items()
            if k in self.meta.fields or k in self.meta.model_references
        }

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
        return bool(
            self.meta.registry
            and not self.meta.abstract
            and all(self.__dict__.get(field) is not None for field in self.identifying_db_fields)
        )

    async def load_recursive(
        self,
        only_needed: bool = False,
        only_needed_nest: bool = False,
        _seen: Optional[Set[Any]] = None,
    ) -> None:
        if _seen is None:
            _seen = {self.create_model_key()}
        else:
            model_key = self.create_model_key()
            if model_key in _seen:
                return
            else:
                _seen.add(model_key)
        _loaded_or_deleted = self._loaded_or_deleted
        if self.can_load:
            await self.load(only_needed)
        if only_needed_nest and _loaded_or_deleted:
            return
        for field_name in self.meta.foreign_key_fields:
            value = getattr(self, field_name, None)
            if value is not None:
                # if a subinstance is fully loaded stop
                await value.load_recursive(
                    only_needed=only_needed, only_needed_nest=True, _seen=_seen
                )

    @property
    def signals(self) -> "Broadcaster":
        warnings.warn(
            "'signals' has been deprecated, use 'meta.signals' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.meta.signals

    @property
    def fields(self) -> Dict[str, "BaseFieldType"]:
        warnings.warn(
            "'fields' has been deprecated, use 'meta.fields' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.meta.fields

    @property
    def table(self) -> sqlalchemy.Table:
        if getattr(self, "_table", None) is None:
            return cast("sqlalchemy.Table", self.__class__.table)
        return self._table

    @table.setter
    def table(self, value: sqlalchemy.Table) -> None:
        with contextlib.suppress(AttributeError):
            del self._pknames
        with contextlib.suppress(AttributeError):
            del self._pkcolumns
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
            field = self.meta.fields.get(field_name)
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

        fields = {key: copy.copy(field) for key, field in cls.meta.fields.items()}
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
            field: BaseFieldType = self.meta.fields[field_name]
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
                retval = retval.model_dump(
                    include=sub_include, exclude=sub_exclude, mode=mode, **kwargs
                )
            else:
                assert (
                    sub_include is None
                ), "sub include filters for CompositeField specified, but no Pydantic model is set"
                assert (
                    sub_exclude is None
                ), "sub exclude filters for CompositeField specified, but no Pydantic model is set"
                if mode == "json" and not getattr(field, "unsafe_json_serialization", False):
                    # skip field if it isn't a BaseModel and the mode is json and unsafe_json_serialization is not set
                    # currently unsafe_json_serialization exists only on CompositeFields
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

        columns: List[sqlalchemy.Column] = []
        global_constraints: List[Any] = []
        for name, field in cls.meta.fields.items():
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

    def __setattr__(self, key: str, value: Any) -> None:
        fields = self.meta.fields
        field = fields.get(key, None)
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

    async def _agetattr_helper(self, name: str) -> Any:
        await self.load()
        return self.__dict__[name]

    def __getattr__(self, name: str) -> Any:
        """
        Does following things
        1. Initialize managers on access
        2. Redirects get accesses to getter fields
        3. Run an one off query to populate any foreign key making sure
           it runs only once per foreign key avoiding multiple database calls.
        """
        return_load_coro_on_attr_access = self._return_load_coro_on_attr_access
        # unset flag
        self._return_load_coro_on_attr_access = False
        manager = self.meta.managers.get(name)
        if manager is not None:
            if name not in self.__dict__:
                manager = copy.copy(manager)
                manager.instance = self
                self.__dict__[name] = manager
            return self.__dict__[name]

        field = self.meta.fields.get(name)
        if field is not None and hasattr(field, "__get__"):
            # no need to set an descriptor object
            return field.__get__(self, self.__class__)
        if (
            name not in self.__dict__
            and not self._loaded_or_deleted
            and field is not None
            and name not in self.identifying_db_fields
            and self.can_load
        ):
            coro = self._agetattr_helper(name)
            if return_load_coro_on_attr_access:
                return coro
            return run_sync(coro)
        return super().__getattr__(name)

    def __eq__(self, other: Any) -> bool:
        # if self.__class__ != other.__class__:
        #     return False
        # somehow meta gets regenerated, so just compare tablename and registry.
        if self.meta.registry is not other.meta.registry:
            return False
        if self.meta.tablename != other.meta.tablename:
            return False
        self_dict = self.extract_column_values(
            self.extract_db_fields(self.pkcolumns), is_partial=True
        )
        other_dict = self.extract_column_values(
            other.extract_db_fields(self.pkcolumns), is_partial=True
        )
        key_set = {*self_dict.keys(), *other_dict.keys()}
        for field_name in key_set:
            if self_dict.get(field_name) != other_dict.get(field_name):
                return False
        return True
