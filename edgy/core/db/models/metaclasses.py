import copy
import inspect
from collections import UserDict, deque
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Dict,
    FrozenSet,
    List,
    Optional,
    Sequence,
    Tuple,
    Type,
    Union,
    cast,
    get_origin,
)

import sqlalchemy
from pydantic._internal._model_construction import ModelMetaclass

from edgy.core import signals as signals_module
from edgy.core.connection.registry import Registry
from edgy.core.db import fields as edgy_fields
from edgy.core.db.datastructures import Index, UniqueConstraint
from edgy.core.db.fields.base import BaseField, PKField
from edgy.core.db.fields.foreign_keys import BaseForeignKeyField
from edgy.core.db.fields.many_to_many import BaseManyToManyForeignKeyField
from edgy.core.db.fields.ref_foreign_key import BaseRefForeignKeyField
from edgy.core.db.models.managers import BaseManager
from edgy.core.db.models.utils import build_pkcolumns, build_pknames
from edgy.core.db.relationships.related_field import RelatedField
from edgy.core.utils.functional import extract_field_annotations_and_defaults
from edgy.exceptions import ForeignKeyBadConfigured, ImproperlyConfigured

if TYPE_CHECKING:
    from edgy.core.db.models import Model, ModelRef, ReflectModel

_empty_dict: Dict[str, Any] = {}
_empty_set: FrozenSet[Any] = frozenset()

class FieldToColumns(UserDict, Dict[str, Sequence["sqlalchemy.Column"]]):
    def __init__(self, meta: "MetaInfo"):
        self.meta = meta
        super().__init__()

    def __getitem__(self, name: str) -> Sequence["sqlalchemy.Column"]:
        if name in self.data:
            return cast(Sequence["sqlalchemy.Column"], self.data[name])
        field = self.meta.fields_mapping[name]
        result = self.data[name] = field.get_columns(name)
        return result

    def __setitem__(self, name: str, value: Any) -> None:
        raise Exception("Cannot set item here")

    def __iter__(self) -> Any:
        self.meta.columns_to_field.init()
        return super().__iter__()

    def __contains__(self, key: str) -> bool:
        try:
            self[key]
            return True
        except KeyError:
            return False


class FieldToColumnNames(FieldToColumns, Dict[str, FrozenSet[str]]):
    def __getitem__(self, name: str) -> FrozenSet[str]:
        if name in self.data:
            return cast(FrozenSet[str], self.data[name])
        column_names = frozenset(column.name for column in self.meta.field_to_columns[name])
        result = self.data[name] = column_names
        return result


class ColumnsToField(UserDict, Dict[str, str]):
    def __init__(self, meta: "MetaInfo"):
        self.meta = meta
        self._init = False
        super().__init__()

    def init(self) -> None:
        if not self._init:
            self._init = True
            _columns_to_field: Dict[str, str] = {}
            for field_name in self.meta.fields_mapping.keys():
                # init structure
                column_names = self.meta.field_to_column_names[field_name]
                for column_name in column_names:
                    if column_name in _columns_to_field:
                        raise ValueError(f"column collision: {column_name} between field {field_name} and {_columns_to_field[column_name]}")
                    _columns_to_field[column_name] = field_name
            self.data.update(_columns_to_field)

    def __getitem__(self, name: str) -> str:
        self.init()
        return cast(str, super().__getitem__(name))

    def __setitem__(self, name: str, value: Any) -> None:
        raise Exception("Cannot set item here")

    def __contains__(self, name: str) -> bool:
        self.init()
        return super().__contains__(name)


_trigger_attributes_MetaInfo = {
    "field_to_columns",
    "field_to_column_names",
    "foreign_key_fields",
    "columns_to_field",
    "special_getter_fields",
    "input_modifying_fields",
    "excluded_fields",
}

class MetaInfo:
    __slots__ = (
        "abstract",
        "inherit",
        "fields_mapping",
        "registry",
        "tablename",
        "unique_together",
        "indexes",
        "parents",
        "model",
        "managers",
        "multi_related",
        "model_references",
        "signals",
        "input_modifying_fields",
        "foreign_key_fields",
        "field_to_columns",
        "field_to_column_names",
        "columns_to_field",
        "special_getter_fields",
        "excluded_fields",
        "_is_init"
    )
    _include_dump = (*filter(lambda x: x not in {
        "field_to_columns",
        "field_to_column_names",
        "columns_to_field",
        "_is_init"
    }, __slots__), "pk", "is_multi")

    field_to_columns: FieldToColumns
    field_to_column_names: FieldToColumnNames
    columns_to_field: Dict[str, str]

    def __init__(self, meta: Any = None, **kwargs: Any) -> None:
        #  Difference between meta extraction and kwargs: meta attributes are copied
        self.abstract: bool = getattr(meta, "abstract", False)
        # for embedding
        self.inherit: bool = getattr(meta, "inherit", True)
        self.registry: Optional[Registry] = getattr(meta, "registry", None)
        self.tablename: Optional[str] = getattr(meta, "tablename", None)
        self.unique_together: Any = getattr(meta, "unique_together", None)
        self.indexes: Any = getattr(meta, "indexes", None)
        self.signals = signals_module.Broadcaster(getattr(meta, "signals", None) or {})
        self.signals.set_lifecycle_signals_from(signals_module, overwrite=False)
        self.parents: List[Any] = [*getattr(meta, "parents", _empty_set)]
        self.fields_mapping: Dict[str, BaseField] = {**getattr(meta, "fields_mapping", _empty_dict)}
        self.model_references: Dict[str, "ModelRef"] = {**getattr(meta, "model_references", _empty_dict)}
        self.managers: Dict[str, BaseManager] = {**getattr(meta, "managers", _empty_dict)}
        self.multi_related: List[str] =  [*getattr(meta, "multi_related", _empty_set)]
        self.model: Optional[Type["Model"]] = None
        self.load_dict(kwargs)

    @property
    def pk(self) -> Optional[PKField]:
        return cast(Optional[PKField], self.fields_mapping.get("pk"))

    @property
    def is_multi(self) -> bool:
        return bool(self.multi_related)

    def model_dump(self) -> Dict[Any, Any]:
        return {k: getattr(self, k, None) for k in self._include_dump}

    def load_dict(self, values: Dict[str, Any], _init: bool=False) -> None:
        """
        Loads the metadata from a dictionary.
        """
        for key, value in values.items():
            # we want triggering invalidate in case it is fields_mapping
            setattr(self, key, value)

    def __setattr__(self, name: str, value: Any) -> None:
        super().__setattr__(name, value)
        if name == "fields_mapping":
            self.invalidate()

    def __getattribute__(self, name: str) -> Any:
        # lazy execute
        if name in _trigger_attributes_MetaInfo and not self._is_init:
            self.init_fields_mapping()
        return super().__getattribute__(name)

    def init_fields_mapping(self) -> None:
        special_getter_fields = set()
        excluded_fields = set()
        input_modifying_fields = set()
        foreign_key_fields: Dict[str, BaseField] = {}
        for key, field in self.fields_mapping.items():
            if hasattr(field, "__get__"):
                special_getter_fields.add(key)
            if getattr(field, "exclude", False):
                excluded_fields.add(key)
            if hasattr(field, "modify_input"):
                input_modifying_fields.add(key)
            if isinstance(field, BaseForeignKeyField):
                foreign_key_fields[key] = field
        self.special_getter_fields: FrozenSet[str] = frozenset(special_getter_fields)
        self.excluded_fields: FrozenSet[str] = frozenset(excluded_fields)
        self.input_modifying_fields: FrozenSet[str] = frozenset(input_modifying_fields)
        self.foreign_key_fields: Dict[str, BaseField] = foreign_key_fields
        self.field_to_columns = FieldToColumns(self)
        self.field_to_column_names = FieldToColumnNames(self)
        self.columns_to_field = ColumnsToField(self)
        self._is_init = True

    def invalidate(self, clear_class_attrs: bool=True) -> None:
        self._is_init = False
        # prevent cycles and mem-leaks
        self.field_to_columns = FieldToColumns(self)
        self.field_to_column_names = FieldToColumnNames(self)
        self.columns_to_field = ColumnsToField(self)
        if clear_class_attrs:
            for attr in ("_table", "_pknames", "_pkcolumns"):
                try:
                    delattr(self.model, attr)
                except AttributeError:
                    pass

    def full_init(self, init_column_mappers: bool=True, init_class_attrs: bool=True) -> None:
        if not self._is_init:
            self.init_fields_mapping()
        if init_column_mappers:
            self.columns_to_field.init()
        if init_class_attrs:
            for attr in ("table", "pknames", "pkcolumns"):
                getattr(self.model, attr)

    def get_columns_for_name(self, name: str) -> Sequence["sqlalchemy.Column"]:
        if name in self.field_to_columns:
            return self.field_to_columns[name]
        elif self.model and name in self.model.table.columns:
            return (self.model.table.columns[name],)
        else:
            return cast(Sequence["sqlalchemy.Column"], _empty_set)


def get_model_registry(
    bases: Tuple[Type, ...], meta_class: Optional[Union["object", MetaInfo]] = None
) -> Optional[Registry]:
    """
    When a registry is missing from the Meta class, it should look up for the bases
    and obtain the first found registry.
    """
    if meta_class is not None:
        direct_registry: Optional[Registry] = getattr(meta_class, "registry", None)
        if direct_registry is not None:
            return direct_registry

    for base in bases:
        meta: MetaInfo = getattr(base, "meta", None)  # type: ignore
        if not meta:
            continue
        found_registry: Optional[Registry] = getattr(meta, "registry", None)

        if found_registry is not None:
            return found_registry
    return None


def _set_related_name_for_foreign_keys(
    foreign_keys: Dict[str, BaseForeignKeyField],
    model_class: Union["Model", "ReflectModel"],
) -> None:
    """
    Sets the related name for the foreign keys.
    When a `related_name` is generated, creates a RelatedField from the table pointed
    from the ForeignKey declaration and the the table declaring it.
    """
    if not foreign_keys:
        return

    for name, foreign_key in foreign_keys.items():
        related_name = getattr(foreign_key, "related_name", None)
        if related_name is False:
            # skip related_field
            continue

        if not related_name:
            if foreign_key.unique:
                related_name = f"{model_class.__name__.lower()}"
            else:
                related_name = f"{model_class.__name__.lower()}s_set"

        if related_name in foreign_key.target.meta.fields_mapping:
            raise ForeignKeyBadConfigured(
                f"Multiple related_name with the same value '{related_name}' found to the same target. Related names must be different."
            )
        foreign_key.related_name = related_name
        foreign_key.reverse_name = related_name

        related_field = RelatedField(
            foreign_key_name=name,
            name=related_name,
            owner=foreign_key.target,
            related_from=model_class,
        )

        # Set the related name
        target = foreign_key.target
        target.meta.fields_mapping[related_name] = related_field


def _handle_annotations(base: Type, base_annotations: Dict[str, Any]) -> None:
    for parent in base.__mro__[1:]:
        _handle_annotations(parent, base_annotations)
    if hasattr(base, "__init_annotations__") and base.__init_annotations__:
        base_annotations.update(base.__init_annotations__)
    elif hasattr(base, "__annotations__") and base.__annotations__:
        base_annotations.update(base.__annotations__)


def handle_annotations(
    bases: Tuple[Type, ...], base_annotations: Dict[str, Any], attrs: Any
) -> Dict[str, Any]:
    """
    Handles and copies some of the annotations for
    initialiasation.
    """
    for base in bases:
        _handle_annotations(base, base_annotations)

    annotations: Dict[str, Any] = (
        copy.copy(attrs["__init_annotations__"])
        if "__init_annotations__" in attrs
        else copy.copy(attrs["__annotations__"])
    )
    annotations.update(base_annotations)
    return annotations


_occluded_sentinel = object()

def _extract_fields_and_managers(base: Type, attrs: Dict[str, Any]) -> None:
    from edgy.core.db.fields.composite_field import CompositeField
    meta: Union[MetaInfo, None] = getattr(base, "meta", None)
    if not meta:
        # Mixins and other classes
        # Note: from mixins BaseFields and BaseManagers are imported despite inherit=False until a model in the
        # hierarchy uses them
        # Here is _occluded_sentinel not overwritten
        for key, value in inspect.getmembers(base):
            if key not in attrs:
                if isinstance(value, BaseField):
                    attrs[key] = value
                elif isinstance(value, BaseManager):
                    attrs[key] = value.__class__()
                elif isinstance(value, BaseModelMeta):
                    attrs[key] = CompositeField(inner_fields=value, prefix_embedded=f"{key}_", inherit=value.meta.inherit, name=key, owner=value)
            elif attrs[key] is _occluded_sentinel:
                # when occluded only include if inherit is True
                if isinstance(value, BaseField) and value.inherit:
                    attrs[key] = value
                elif isinstance(value, BaseManager) and value.inherit:
                    attrs[key] = value.__class__()
                elif isinstance(value, BaseModelMeta) and value.meta.inherit:
                    attrs[key] = CompositeField(inner_fields=value, prefix_embedded=f"{key}_", inherit=value.meta.inherit, name=key, owner=value)

    else:
        # abstract classes
        for key, value in meta.fields_mapping.items():
            if key not in attrs:
                # when abstract or inherit passthrough
                if meta.abstract or value.inherit:
                    attrs[key] = value
                    assert value.owner is not None
                else:
                    attrs[key] = _occluded_sentinel
            elif attrs[key] is _occluded_sentinel and value.inherit:
                # when occluded only include if inherit is True
                attrs[key] = value
                assert value.owner is not None
        for key, value in meta.managers.items():
            if key not in attrs:
                # when abstract or inherit passthrough
                if meta.abstract or value.inherit:
                    attrs[key] = value
                else:
                    attrs[key] = _occluded_sentinel
            elif attrs[key] is _occluded_sentinel and value.inherit:
                # when occluded only include if inherit is True
                attrs[key] = value

    # from strongest to weakest
    for parent in base.__mro__[1:]:
        _extract_fields_and_managers(parent, attrs)


def extract_fields_and_managers(bases: Sequence[Type], attrs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Search for fields and managers and return them.

    Managers are copied.

    Note: managers and fields with inherit=False are still extracted from mixins as long there is no intermediate model
    """

    from edgy.core.db.fields.composite_field import CompositeField
    attrs = {} if attrs is None else {**attrs}
    # order is important
    for key in list(attrs.keys()):
        value = attrs[key]
        if isinstance(value, BaseModelMeta):
            value = attrs[key]
            attrs[key] = CompositeField(inner_fields=value, prefix_embedded=f"{key}_", inherit=value.meta.inherit, owner=value)
    for base in bases:
        _extract_fields_and_managers(base, attrs)
    # now remove sentinels
    for key in list(attrs.keys()):
        value = attrs[key]
        if value is _occluded_sentinel:
            attrs.pop(key)
    return attrs


class BaseModelMeta(ModelMetaclass):
    __slots__ = ()

    def __new__(cls, name: str, bases: Tuple[Type, ...], attrs: Dict[str, Any]) -> Any:
        fields: Dict[str, BaseField] = {}
        model_references: Dict[str, "ModelRef"] = {}
        managers: Dict[str, BaseManager] = {}
        meta_class: "object" = attrs.get("Meta", type("Meta", (), {}))
        base_annotations: Dict[str, Any] = {}
        has_explicit_primary_key = False
        registry: Optional[Registry] = get_model_registry(bases, meta_class)
        is_abstract: bool = getattr(meta_class, "abstract", False)
        parents = [parent for parent in bases if isinstance(parent, BaseModelMeta)]

        # Extract the custom Edgy Fields in a pydantic format.
        attrs, model_fields = extract_field_annotations_and_defaults(attrs)

        # Extract fields and managers and include them in attrs
        attrs = extract_fields_and_managers(bases, attrs)

        for key, value in attrs.items():
            if isinstance(value, BaseField):
                if key == "pk" and not isinstance(value, PKField):
                    raise ImproperlyConfigured(
                        f"Cannot add a field named pk to model {name}. Protected name."
                    )
                # make sure we have a fresh copy where we can set the owner
                value = copy.copy(value)
                if value.primary_key:
                    has_explicit_primary_key = True
                # set as soon as possible the field_name
                value.name = key
                if registry:
                    value.registry = registry

                # add fields and non BaseRefForeignKeyField to fields
                # The BaseRefForeignKeyField is actually not a normal SQL Foreignkey
                # It is an Edgy specific operation that creates a reference to a ForeignKey
                # That is why is not stored as a normal FK but as a reference but
                # stored also as a field to be able later or to access anywhere in the model
                # and use the value for the creation of the records via RefForeignKey.
                # This is then used in `save_model_references()` and `update_model_references
                # saving a reference foreign key.
                # We split the keys (store them) in different places to be able to easily maintain and
                #  what is what.
                if isinstance(value, BaseRefForeignKeyField):
                    model_references[key] = value.to
                else:
                    fields[key] = value
            elif isinstance(value, BaseManager):
                value = copy.copy(value)
                value.name = key
                managers[key] = value

        if not is_abstract:
            # the order is important because it reflects the inheritance order
            # from the strongest to the weakest
            fieldnames_to_check = deque(fields.keys())
            while fieldnames_to_check:
                # pop the weakest next field
                field_name = fieldnames_to_check.pop()
                field = fields[field_name]
                embedded_fields = field.get_embedded_fields(field_name, fields)
                if embedded_fields:
                    for sub_field_name, sub_field in embedded_fields.items():
                        if sub_field_name == "pk":
                            raise ValueError("sub field uses reserved name pk")

                        if sub_field_name in fields and fields[sub_field_name].owner is None:
                            raise ValueError(f"sub field name collision: {sub_field_name}")
                        # set as soon as possible the field_name
                        sub_field.name = sub_field_name
                        if registry:
                            sub_field.registry = registry
                        if sub_field.primary_key:
                            has_explicit_primary_key = True
                        # insert as stronger element
                        fieldnames_to_check.appendleft(sub_field_name)
                        fields[sub_field_name] = sub_field
                        model_fields[sub_field_name] = sub_field
            # Handle with multiple primary keys and auto generated field if no primary key is provided
            if not is_abstract and parents and registry and not has_explicit_primary_key:
                if "id" not in fields:
                    if attrs.get("__reflected__", False):
                        raise ImproperlyConfigured(
                            f"Cannot create model {name}. No primary key found and reflected."
                        )
                    else:
                        fields["id"] = edgy_fields.BigIntegerField(
                            primary_key=True, autoincrement=True, inherit=False, name="id"
                        )  # type: ignore
                if not isinstance(fields["id"], BaseField) or not fields["id"].primary_key:
                    raise ImproperlyConfigured(
                        f"Cannot create model {name} without explicit primary key if field 'id' is already present."
                    )

        for field_name in fields:
            attrs.pop(field_name, None)

        for manager_name in managers:
            attrs.pop(manager_name, None)

        attrs["meta"] = meta = MetaInfo(meta_class, fields_mapping=fields, model_references=model_references, parents=parents, managers=managers)
        if is_abstract:
            meta.abstract = True

        del is_abstract
        if not fields:
            meta.abstract = True

        if not meta.abstract:
            fields["pk"] = PKField(
                exclude=True,
                name="pk",
                inherit=False
            )

        model_class = super().__new__

        # Handle annotations
        annotations: Dict[str, Any] = handle_annotations(bases, base_annotations, attrs)

        for k, _ in meta.managers.items():
            if annotations and k not in annotations:
                raise ImproperlyConfigured(
                    f"Managers must be type annotated and '{k}' is not annotated. Managers must be annotated with ClassVar."
                )
            if annotations and get_origin(annotations[k]) is not ClassVar:
                raise ImproperlyConfigured("Managers must be ClassVar type annotated.")

        # Ensure the initialization is only performed for subclasses of EdgyBaseModel
        attrs["__init_annotations__"] = annotations

        # Ensure initialization is only performed for subclasses of EdgyBaseModel
        # (excluding the EdgyBaseModel class itself).
        if not parents:
            return model_class(cls, name, bases, attrs)

        new_class = cast("Type[Model]", model_class(cls, name, bases, attrs))
        new_class.fields = fields

        # Update the model_fields are updated to the latest
        new_class.model_fields = {**new_class.model_fields, **model_fields}

        # Set the owner of the field, must be done as early as possible
        # don't use meta.fields_mapping to not trigger the lazy evaluation
        for value in fields.values():
            value.owner = new_class
        # set the model_class of managers
        for value in meta.managers.values():
            value.owner = new_class


        # Validate meta for uniques and indexes
        if meta.abstract:
            if getattr(meta, "unique_together", None) is not None:
                raise ImproperlyConfigured("unique_together cannot be in abstract classes.")

            if getattr(meta, "indexes", None) is not None:
                raise ImproperlyConfigured("indexes cannot be in abstract classes.")

        # Now set the registry of models
        if meta.registry is None:
            if getattr(new_class, "__db_model__", False):
                meta.registry = registry
            else:
                new_class.model_rebuild(force=True)
                return new_class
        if registry is None:
            raise ImproperlyConfigured(
                "Registry for the table not found in the Meta class or any of the superclasses. You must set the registry in the Meta."
            )


        new_class.database = registry.database

        # Making sure the tablename is always set if the value is not provided
        if getattr(meta, "tablename", None) is None:
            tablename = f"{name.lower()}s"
            meta.tablename = tablename

        if getattr(meta, "unique_together", None) is not None:
            unique_together = meta.unique_together
            if not isinstance(unique_together, (list, tuple)):
                value_type = type(unique_together).__name__
                raise ImproperlyConfigured(
                    f"unique_together must be a tuple or list. Got {value_type} instead."
                )
            else:
                for value in unique_together:
                    if not isinstance(value, (str, tuple, UniqueConstraint)):
                        raise ValueError(
                            "The values inside the unique_together must be a string, a tuple of strings or an instance of UniqueConstraint."
                        )

        # Handle indexes
        if getattr(meta, "indexes", None) is not None:
            indexes = meta.indexes
            if not isinstance(indexes, (list, tuple)):
                value_type = type(indexes).__name__
                raise ImproperlyConfigured(
                    f"indexes must be a tuple or list. Got {value_type} instead."
                )
            else:
                for value in indexes:
                    if not isinstance(value, Index):
                        raise ValueError("Meta.indexes must be a list of Index types.")

        for value in fields.values():
            if isinstance(value, BaseManyToManyForeignKeyField):
                value.create_through_model()

        # Making sure it does not generate tables if abstract it set
        if not meta.abstract:
            if getattr(cls, "__reflected__", False):
                registry.reflected[name] = new_class
            else:
                registry.models[name] = new_class

        new_class.__db_model__ = True
        meta.model = new_class

        # Sets the foreign key fields
        if not new_class.is_proxy_model and meta.foreign_key_fields:
            _set_related_name_for_foreign_keys(meta.foreign_key_fields, new_class)

        # Update the model references with the validations of the model
        # Being done by the Edgy fields instead.
        # Generates a proxy model for each model created
        # Making sure the core model where the fields are inherited
        # And mapped contains the main proxy_model
        if not new_class.is_proxy_model and not meta.abstract:
            proxy_model = new_class.generate_proxy_model()
            new_class.__proxy_model__ = proxy_model
            new_class.__proxy_model__.parent = new_class
            new_class.__proxy_model__.model_rebuild(force=True)
            meta.registry.models[new_class.__name__] = new_class  # type: ignore

        # finalize
        new_class.model_rebuild(force=True)

        return new_class

    def get_db_shema(cls) -> Union[str, None]:
        """
        Returns a db_schema from registry if any is passed.
        """
        if hasattr(cls, "meta") and hasattr(cls.meta, "registry"):
            return cast(str, cls.meta.registry.db_schema)
        elif hasattr(cls, "__using_schema__") and cls.__using_schema__ is not None:
            return cast(str, cls.__using_schema__)
        return None

    @property
    def table(cls) -> Any:
        """
        Making sure the tables on inheritance state, creates the new
        one properly.

        Making sure the following scenarios are met:

        1. If there is a context_db_schema, it will return for those, which means, the `using`
        if being utilised.
        2. If a db_schema in the `registry` is passed, then it will use that as a default.
        3. If none is passed, defaults to the shared schema of the database connected.
        """
        if not hasattr(cls, "_table"):
            cls._table = cls.build(cls.get_db_shema())
        elif hasattr(cls, "_table"):
            table = cls._table
            if table.name.lower() != cls.meta.tablename:
                cls._table = cls.build(cls.get_db_shema())
        return cls._table

    @table.setter
    def table(cls, value: sqlalchemy.Table) -> None:
        try:
            del cls._pknames
        except AttributeError:
            pass
        try:
            del cls._pkcolumns
        except AttributeError:
            pass
        cls._table = value

    def __getattr__(cls, name: str) -> Any:
        """
        For controlling inheritance we cannot have manager descriptors, so fake them
        """
        manager = cls.meta.managers.get(name)
        if manager is not None:
            return manager
        return super().__getattr__(name)


    @property
    def pkcolumns(cls) -> Sequence[str]:
        if cls.__dict__.get("_pkcolumns", None) is None:
            build_pkcolumns(cls)
        return cast(Sequence[str], cls._pkcolumns)

    @property
    def pknames(cls) -> Sequence[str]:
        if cls.__dict__.get("_pknames", None) is None:
            build_pknames(cls)
        return cast(Sequence[str], cls._pknames)

    @property
    def signals(cls) -> signals_module.Broadcaster:
        """
        Returns the signals of a class
        """
        meta: MetaInfo = cls.meta
        return meta.signals

    def table_schema(cls, schema: str) -> Any:
        """
        Making sure the tables on inheritance state, creates the new
        one properly.

        The use of context vars instead of using the lru_cache comes from
        a warning from `ruff` where lru can lead to memory leaks.
        """
        return cls.build(schema=schema)

    @property
    def proxy_model(cls) -> Any:
        """
        Returns the proxy_model from the Model when called using the cache.
        """
        return cls.__proxy_model__

    @property
    def columns(cls) -> sqlalchemy.sql.ColumnCollection:
        return cast("sqlalchemy.sql.ColumnCollection", cls.table.columns)
