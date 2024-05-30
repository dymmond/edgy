import copy
import inspect
from collections import deque
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Dict,
    FrozenSet,
    List,
    Optional,
    Sequence,
    Set,
    Tuple,
    Type,
    Union,
    cast,
    get_origin,
)

import sqlalchemy
from pydantic._internal._model_construction import ModelMetaclass

from edgy.conf import settings
from edgy.core import signals as signals_module
from edgy.core.connection.registry import Registry
from edgy.core.db import fields as edgy_fields
from edgy.core.db.constants import ConditionalRedirect
from edgy.core.db.datastructures import Index, UniqueConstraint
from edgy.core.db.fields.base import BaseField
from edgy.core.db.fields.core import ConcreteCompositeField
from edgy.core.db.fields.foreign_keys import BaseForeignKeyField
from edgy.core.db.fields.many_to_many import BaseManyToManyForeignKeyField
from edgy.core.db.fields.one_to_one_keys import BaseOneToOneKeyField
from edgy.core.db.fields.ref_foreign_key import BaseRefForeignKeyField
from edgy.core.db.models.managers import Manager
from edgy.core.db.relationships.related_field import RelatedField
from edgy.core.db.relationships.relation import Relation
from edgy.core.utils.functional import edgy_setattr, extract_field_annotations_and_defaults
from edgy.exceptions import ForeignKeyBadConfigured, ImproperlyConfigured

if TYPE_CHECKING:
    from edgy.core.db.models import Model, ModelRef, ReflectModel

_empty_dict: Dict[str, Any] = {}
_empty_set: FrozenSet[Any] = frozenset()


class MetaInfo:
    __slots__ = (
        "pk",
        "pk_attributes",
        "abstract",
        "fields",
        "fields_mapping",
        "registry",
        "tablename",
        "unique_together",
        "indexes",
        "foreign_key_fields",
        "parents",
        "many_to_many_fields",
        "manager",
        "model",
        "reflect",
        "managers",
        "is_multi",
        "multi_related",
        "related_names",
        "related_fields",
        "model_references",
        "related_names_mapping",
        "signals",
    )

    def __init__(self, meta: Any = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.pk: Optional[BaseField] = getattr(meta, "pk", None)
        self.pk_attributes: Sequence[str] = getattr(meta, "pk_attributes", "")
        self.abstract: bool = getattr(meta, "abstract", False)
        self.fields: Set[Any] = {*getattr(meta, "fields", _empty_set)}
        self.fields_mapping: Dict[str, BaseField] = {**getattr(meta, "fields_mapping", _empty_dict)}
        self.registry: Optional[Registry] = getattr(meta, "registry", None)
        self.tablename: Optional[str] = getattr(meta, "tablename", None)
        self.parents: List[Any] = [*getattr(meta, "parents", _empty_set)]
        self.many_to_many_fields: Set[str] = {*getattr(meta, "many_to_many_fields", _empty_set)}
        self.foreign_key_fields: Dict[str, Any] = {**getattr(meta, "foreign_key_fields", _empty_dict)}
        self.model_references: Dict["ModelRef", str] = {**getattr(meta, "model_references", _empty_dict)}
        self.model: Optional[Type["Model"]] = None
        self.manager: "Manager" = getattr(meta, "manager", Manager())
        self.managers: List[Manager] = [*getattr(meta, "managers", _empty_set)]
        self.unique_together: Any = getattr(meta, "unique_together", None)
        self.indexes: Any = getattr(meta, "indexes", None)
        self.reflect: bool = getattr(meta, "reflect", False)
        self.is_multi: bool = getattr(meta, "is_multi", False)
        self.multi_related: Sequence[str] = [*getattr(meta, "multi_related", _empty_set)]
        self.related_names: Set[str] = {*getattr(meta, "related_names", _empty_set)}
        self.related_fields: Dict[str, Any] = {**getattr(meta, "related_fields", _empty_dict)}
        self.related_names_mapping: Dict[str, Any] = {**getattr(meta, "related_names_mapping", _empty_dict)}
        self.signals: Optional[signals_module.Broadcaster] = signals_module.Broadcaster(
            **getattr(meta, "signals", _empty_dict)
        )

        for k, v in kwargs.items():
            edgy_setattr(self, k, v)

    def model_dump(self) -> Dict[Any, Any]:
        return {k: getattr(self, k, None) for k in self.__slots__}

    def load_dict(self, values: Dict[str, Any]) -> None:
        """
        Loads the metadata from a dictionary
        """
        for key, value in values.items():
            edgy_setattr(self, key, value)


def _check_model_inherited_registry(bases: Tuple[Type, ...]) -> Registry:
    """
    When a registry is missing from the Meta class, it should look up for the bases
    and obtain the first found registry.

    If not found, then a ImproperlyConfigured exception is raised.
    """
    found_registry: Optional[Registry] = None

    for base in bases:
        meta: MetaInfo = getattr(base, "meta", None)  # type: ignore
        if not meta:
            continue

        if getattr(meta, "registry", None) is not None:
            found_registry = meta.registry
            break

    if not found_registry:
        raise ImproperlyConfigured(
            "Registry for the table not found in the Meta class or any of the superclasses. You must set the registry in the Meta."
        )
    return found_registry


def _check_manager_for_bases(
    base: Tuple[Type, ...],
    attrs: Any,
    meta: Optional[MetaInfo] = None,
    is_check: bool = False,
) -> None:
    """
    When an abstract class is declared, we must treat the manager's value coming from the top.
    """
    if not meta or (meta and not meta.abstract):
        for key, value in inspect.getmembers(base):
            if isinstance(value, Manager) and key not in attrs:
                if key not in base.__class_vars__:
                    raise ImproperlyConfigured(
                        f"Managers must be type annotated and '{key}' is not annotated. Managers must be annotated with ClassVar."
                    )
                if get_origin(base.__annotations__[key]) is not ClassVar:
                    raise ImproperlyConfigured("Managers must be ClassVar type annotated.")
                attrs[key] = value.__class__()


def _set_related_name_for_foreign_keys(
    foreign_keys: Set[Union[edgy_fields.OneToOneField, edgy_fields.ForeignKey]],
    model_class: Union["Model", "ReflectModel"],
) -> Union[str, None]:
    """
    Sets the related name for the foreign keys.
    When a `related_name` is generated, creates a RelatedField from the table pointed
    from the ForeignKey declaration and the the table declaring it.
    """
    if not foreign_keys:
        return None

    for name, foreign_key in foreign_keys.items():
        default_related_name = getattr(foreign_key, "related_name", None)

        if not default_related_name:
            default_related_name = f"{model_class.__name__.lower()}s_set"

        elif hasattr(foreign_key.target, default_related_name):
            raise ForeignKeyBadConfigured(
                f"Multiple related_name with the same value '{default_related_name}' found to the same target. Related names must be different."
            )
        foreign_key.related_name = default_related_name

        related_field = RelatedField(
            related_name=default_related_name,
            related_to=foreign_key.target,
            related_from=model_class,
        )

        # Set the related name
        setattr(foreign_key.target, default_related_name, related_field)
        model_class.meta.related_fields[default_related_name] = related_field

        # Set the fields mapping where a related name maps a specific foreign key
        model_class.meta.related_names_mapping[default_related_name] = name

    return default_related_name


def _set_many_to_many_relation(
    m2m: BaseManyToManyForeignKeyField,
    model_class: Union["Model", "ReflectModel"],
    field: str,
) -> None:
    m2m.create_through_model()
    relation = Relation(through=m2m.through, to=m2m.to, owner=m2m.owner)
    setattr(model_class, settings.many_to_many_relation.format(key=field), relation)


def _register_model_signals(model_class: Type["Model"]) -> None:
    """
    Registers the signals in the model's Broadcaster and sets the defaults.
    """
    signals = signals_module.Broadcaster()
    signals.set_lifecycle_signals_from(signals_module, overwrite=False)
    model_class.meta.signals = signals


def handle_annotations(bases: Tuple[Type, ...], base_annotations: Dict[str, Any], attrs: Any) -> Dict[str, Any]:
    """
    Handles and copies some of the annotations for
    initialiasation.
    """
    for base in bases:
        if hasattr(base, "__init_annotations__") and base.__init_annotations__:
            base_annotations.update(base.__init_annotations__)
        elif hasattr(base, "__annotations__") and base.__annotations__:
            base_annotations.update(base.__annotations__)

    annotations: Dict[str, Any] = (
        copy.copy(attrs["__init_annotations__"])
        if "__init_annotations__" in attrs
        else copy.copy(attrs["__annotations__"])
    )
    annotations.update(base_annotations)
    return annotations


class BaseModelMeta(ModelMetaclass):
    __slots__ = ()

    def __new__(cls, name: str, bases: Tuple[Type, ...], attrs: Any) -> Any:
        fields: Dict[str, BaseField] = {}
        foreign_key_fields: Any = {}
        model_references: Dict["ModelRef", str] = {}
        many_to_many_fields: Any = set()
        meta_class: "object" = attrs.get("Meta", type("Meta", (), {}))
        pk_attributes: Set[str] = set()
        base_annotations: Dict[str, Any] = {}
        is_abstract: bool = getattr(meta_class, "abstract", False)

        # Extract the custom Edgy Fields in a pydantic format.
        attrs, model_fields = extract_field_annotations_and_defaults(attrs)

        # Searching for fields "Field" in the class hierarchy.
        def __search_for_fields(base: Type, attrs: Any) -> None:
            """
            Search for class attributes of the type fields.Field in the given class.

            If a class attribute is an instance of the Field, then it will be added to the
            field_mapping but only if the key does not exist already.

            If a primary_key field is not provided, it it automatically generate one BigIntegerField for the model.
            """
            for parent in base.__mro__[1:]:
                __search_for_fields(parent, attrs)

            meta: Union[MetaInfo, None] = getattr(base, "meta", None)
            if not meta:
                # Mixins and other classes
                for key, value in inspect.getmembers(base):
                    if isinstance(value, BaseField) and key not in attrs:
                        attrs[key] = value

                _check_manager_for_bases(base, attrs)  # type: ignore
            else:
                # abstract classes
                for key, value in meta.fields_mapping.items():
                    attrs[key] = value

                # For managers coming from the top that are not abstract classes
                _check_manager_for_bases(base, attrs, meta)  # type: ignore

        # Search in the base classes
        inherited_fields: Any = {}
        for base in bases:
            __search_for_fields(base, inherited_fields)

        if inherited_fields:
            # Making sure the inherited fields are before the new defined.
            attrs = {**inherited_fields, **attrs}
        else:
            # copy anyway
            attrs = {**attrs}

        # Handle with multiple primary keys and auto generated field if no primary key is provided
        for key, value in attrs.items():
            if isinstance(value, BaseField):
                if key == "pk" and not isinstance(value, ConcreteCompositeField):
                    raise ImproperlyConfigured(f"Cannot add a field named pk to model {name}. Protected name.")
                if value.primary_key:
                    pk_attributes.add(key)

        if not is_abstract:
            if not pk_attributes:
                if "id" not in attrs:
                    attrs["id"] = edgy_fields.BigIntegerField(primary_key=True, autoincrement=True)
                    pk_attributes.add("id")

            if not isinstance(attrs["id"], BaseField) or not attrs["id"].primary_key:
                raise ImproperlyConfigured(
                    f"Cannot create model {name} without explicit primary key if field 'id' is already present."
                )
        for key, value in attrs.items():
            if isinstance(value, BaseField):
                # make sure we have a fresh copy where we can set the owner
                value = copy.copy(value)

                # add fields and non BaseRefForeignKeyField to fields
                # The BaseRefForeignKeyField is actually not a normal SQL Foreignkey
                # It is an Edgy specific operation that creates a reference to a ForeignKey
                # That is why is not stored as a normal FK but as a reference but
                # stored also as a field to be able later or to access anywhere in the model
                # and use the value for the creation of the records via RefForeignKey.
                # This is then used in `save_model_references()` and `update_model_references  saving a reference foreign key.
                # We split the keys (store them) in different places to be able to easily maintain and know what is what.
                if not isinstance(value, BaseRefForeignKeyField):
                    fields[key] = value

                if isinstance(value, BaseOneToOneKeyField):
                    foreign_key_fields[key] = value
                elif isinstance(value, BaseManyToManyForeignKeyField):
                    many_to_many_fields.add(value)
                    continue
                elif isinstance(value, BaseRefForeignKeyField):
                    model_references[key] = value.to
                elif isinstance(value, BaseForeignKeyField):
                    foreign_key_fields[key] = value
                    continue

        if not is_abstract:
            # the order is important because it reflects the inheritance order
            fieldnames_to_check = deque(fields.keys())
            while fieldnames_to_check:
                field_name = fieldnames_to_check.popleft()
                field = fields[field_name]
                # call only when initialized, when inherited this should not be called anymore
                # this way subclasses can overwrite the fields
                if not field.embedded_fields_initialized:
                    field.embedded_fields_initialized = True
                    embedded_fields = field.get_embedded_fields(field_name, fields)
                    if embedded_fields:
                        for sub_field_name, sub_field in embedded_fields.items():
                            if sub_field_name == "pk":
                                raise ValueError("sub field uses reserved name pk")

                            if sub_field_name in fields and fields[sub_field_name].owner is None:
                                raise ValueError(f"sub field name collision: {sub_field_name}")
                            fieldnames_to_check.append(sub_field_name)
                            fields[sub_field_name] = sub_field
                            model_fields[sub_field_name] = sub_field
                            if sub_field.primary_key:
                                pk_attributes.add(sub_field_name)

        for slot in fields:
            attrs.pop(slot, None)

        # create a sorted tuple from pk_attributes for nicer outputs
        pk_attributes_finalized = tuple(sorted(pk_attributes))
        del pk_attributes

        if not is_abstract:
            fields["pk"] = cast(
                BaseField,
                edgy_fields.CompositeField(
                    inner_fields=pk_attributes_finalized, model=ConditionalRedirect, exclude=True
                ),
            )

        del is_abstract

        attrs["meta"] = meta = MetaInfo(meta_class)
        meta.fields_mapping = fields
        meta.foreign_key_fields = foreign_key_fields
        meta.many_to_many_fields = many_to_many_fields
        meta.model_references = model_references
        meta.pk_attributes = pk_attributes_finalized
        meta.pk = fields.get("pk")

        if not fields:
            meta.abstract = True

        model_class = super().__new__

        # Handle annotations
        annotations: Dict[str, Any] = handle_annotations(bases, base_annotations, attrs)

        # Abstract classes do not allow multiple managers. This make sure it is enforced.
        if not meta.abstract:
            meta.managers = {k: v for k, v in attrs.items() if isinstance(v, Manager)}  # type: ignore
            for k, _ in meta.managers.items():
                if annotations and k not in annotations:
                    raise ImproperlyConfigured(
                        f"Managers must be type annotated and '{k}' is not annotated. Managers must be annotated with ClassVar."
                    )
                if annotations and get_origin(annotations[k]) is not ClassVar:
                    raise ImproperlyConfigured("Managers must be ClassVar type annotated.")

        # Ensure the initialization is only performed for subclasses of Model
        attrs["__init_annotations__"] = annotations
        parents = [parent for parent in bases if isinstance(parent, BaseModelMeta)]

        # Ensure initialization is only performed for subclasses of Model
        # (excluding the Model class itself).
        if not parents:
            return model_class(cls, name, bases, attrs)

        meta.parents = parents
        new_class = cast("Type[Model]", model_class(cls, name, bases, attrs))

        # Update the model_fields are updated to the latest
        new_class.model_fields = {**new_class.model_fields, **model_fields}
        new_class.pknames = pk_attributes_finalized

        # Set the owner of the field, must be done as early as possible
        for _, value in fields.items():
            value.owner = new_class

        # Validate meta for managers, uniques and indexes
        if meta.abstract:
            managers = [k for k, v in attrs.items() if isinstance(v, Manager)]
            if len(managers) > 1:
                raise ImproperlyConfigured("Multiple managers are not allowed in abstract classes.")

            if getattr(meta, "unique_together", None) is not None:
                raise ImproperlyConfigured("unique_together cannot be in abstract classes.")

            if getattr(meta, "indexes", None) is not None:
                raise ImproperlyConfigured("indexes cannot be in abstract classes.")

        # Handle the registry of models
        if meta.registry is None:
            if hasattr(new_class, "__db_model__") and new_class.__db_model__:
                meta.registry = _check_model_inherited_registry(bases)
            else:
                new_class.model_rebuild(force=True)
                return new_class

        registry = meta.registry
        assert registry, "no registry found, should not happen here"
        new_class.database = registry.database

        # Making sure the tablename is always set if the value is not provided
        if getattr(meta, "tablename", None) is None:
            tablename = f"{name.lower()}s"
            meta.tablename = tablename

        if getattr(meta, "unique_together", None) is not None:
            unique_together = meta.unique_together
            if not isinstance(unique_together, (list, tuple)):
                value_type = type(unique_together).__name__
                raise ImproperlyConfigured(f"unique_together must be a tuple or list. Got {value_type} instead.")
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
                raise ImproperlyConfigured(f"indexes must be a tuple or list. Got {value_type} instead.")
            else:
                for value in indexes:
                    if not isinstance(value, Index):
                        raise ValueError("Meta.indexes must be a list of Index types.")

        # Set the registry of the field
        for _, value in fields.items():
            value.registry = registry

        # Making sure it does not generate tables if abstract it set
        if not meta.abstract:
            if getattr(cls, "__reflected__", False):
                registry.reflected[name] = new_class
            else:
                registry.models[name] = new_class

        new_class.__db_model__ = True
        new_class.fields = meta.fields_mapping
        meta.model = new_class
        meta.manager.model_class = new_class

        # Set the owner and registry of the field
        for _, value in new_class.fields.items():
            value.owner = new_class
            value.registry = registry

        # Sets the foreign key fields
        if meta.foreign_key_fields and not new_class.is_proxy_model:
            related_name = _set_related_name_for_foreign_keys(meta.foreign_key_fields, new_class)
            meta.related_names.add(related_name)

        for field, value in new_class.fields.items():  # type: ignore
            if isinstance(value, BaseManyToManyForeignKeyField):
                _set_many_to_many_relation(value, new_class, field)

        # Set the manager
        for _, value in attrs.items():
            if isinstance(value, Manager):
                value.model_class = new_class

        # Register the signals
        _register_model_signals(new_class)

        # Update the model references with the validations of the model
        # Being done by the Edgy fields instead.
        # Generates a proxy model for each model created
        # Making sure the core model where the fields are inherited
        # And mapped contains the main proxy_model
        if not new_class.is_proxy_model and not new_class.meta.abstract:
            proxy_model = new_class.generate_proxy_model()
            new_class.__proxy_model__ = proxy_model
            new_class.__proxy_model__.parent = new_class
            new_class.__proxy_model__.model_rebuild(force=True)
            meta.registry.models[new_class.__name__] = new_class

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
        db_schema = cls.get_db_shema()
        if not hasattr(cls, "_table"):
            cls._table = cls.build(db_schema)
        elif hasattr(cls, "_table"):
            table = cls._table
            if table.name.lower() != cls.meta.tablename:
                cls._table = cls.build(db_schema)
        return cls._table

    @table.setter
    def table(self, value: sqlalchemy.Table) -> None:
        self._table = value

    @property
    def signals(cls) -> signals_module.Broadcaster:
        """
        Returns the signals of a class
        """
        return cast(signals_module.Broadcaster, cls.meta.signals)

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
        return cast("sqlalchemy.sql.ColumnCollection", cls._table.columns)
