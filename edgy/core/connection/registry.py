import asyncio
import contextlib
import re
import warnings
from collections import defaultdict
from collections.abc import Container, Generator, Iterable, Sequence
from copy import copy as shallow_copy
from functools import cached_property, partial
from types import TracebackType
from typing import TYPE_CHECKING, Any, Callable, ClassVar, Literal, Optional, Union, cast, overload

import sqlalchemy
from loguru import logger
from sqlalchemy import Engine
from sqlalchemy.ext.asyncio.engine import AsyncEngine
from sqlalchemy.orm import declarative_base as sa_declarative_base

from edgy.conf import evaluate_settings_once_ready
from edgy.core.connection.database import Database, DatabaseURL
from edgy.core.connection.schemas import Schema
from edgy.core.db.context_vars import FORCE_FIELDS_NULLABLE
from edgy.core.utils.sync import current_eventloop, run_sync
from edgy.types import Undefined

from .asgi import ASGIApp, ASGIHelper

if TYPE_CHECKING:
    from edgy.conf.global_settings import EdgySettings
    from edgy.contrib.autoreflection.models import AutoReflectionModel
    from edgy.core.db.fields.types import BaseFieldType
    from edgy.core.db.models.types import BaseModelType


class MetaDataDict(defaultdict[str, sqlalchemy.MetaData]):
    def __init__(self, registry: "Registry") -> None:
        self.registry = registry
        super().__init__(sqlalchemy.MetaData)

    def __getitem__(self, key: Union[str, None]) -> sqlalchemy.MetaData:
        if key not in self.registry.extra and key is not None:
            raise KeyError(f'Extra database "{key}" does not exist.')
        return super().__getitem__(key)

    def get(self, key: str, default: Any = None) -> sqlalchemy.MetaData:
        try:
            return self[key]
        except KeyError:
            return default

    def __copy__(self) -> "MetaDataDict":
        _copy = MetaDataDict(registry=self.registry)
        for k, v in self.items():
            _copy[k] = shallow_copy(v)
        return _copy

    copy = __copy__


class MetaDataByUrlDict(dict):
    def __init__(self, registry: "Registry") -> None:
        self.registry = registry
        super().__init__()
        self.process()

    def process(self) -> None:
        self.clear()
        self[str(self.registry.database.url)] = None
        for k, v in self.registry.extra.items():
            self.setdefault(str(v.url), k)

    def __getitem__(self, key: str) -> sqlalchemy.MetaData:
        translation_name = super().__getitem__(key)
        try:
            return self.registry.metadata_by_name[translation_name]
        except KeyError as exc:
            raise Exception("metadata_by_name returned exception") from exc

    def get(self, key: str, default: Any = None) -> sqlalchemy.MetaData:
        try:
            return self[key]
        except KeyError:
            return default

    def get_name(self, key: str) -> Optional[str]:
        """Return name to url or raise a KeyError in case it isn't available."""
        return cast(Optional[str], super().__getitem__(key))

    def __copy__(self) -> "MetaDataByUrlDict":
        return MetaDataByUrlDict(registry=self.registry)

    copy = __copy__


class Registry:
    """
    The command center for the models of Edgy.
    """

    model_registry_types: ClassVar[tuple[str, ...]] = (
        "models",
        "reflected",
        "tenant_models",
        "pattern_models",
    )

    db_schema: Union[str, None] = None
    content_type: Union[type["BaseModelType"], None] = None
    dbs_reflected: set[Union[str, None]]

    def __init__(
        self,
        database: Union[Database, str, DatabaseURL],
        *,
        with_content_type: Union[bool, type["BaseModelType"]] = False,
        schema: Union[str, None] = None,
        extra: Optional[dict[str, Database]] = None,
        automigrate_config: Union["EdgySettings", None] = None,
        **kwargs: Any,
    ) -> None:
        evaluate_settings_once_ready()
        self.db_schema = schema
        self._automigrate_config = automigrate_config
        self._is_automigrated: bool = False
        extra = extra or {}
        self.database: Database = (
            database if isinstance(database, Database) else Database(database, **kwargs)
        )
        self.models: dict[str, type[BaseModelType]] = {}
        self.reflected: dict[str, type[BaseModelType]] = {}
        self.tenant_models: dict[str, type[BaseModelType]] = {}
        self.pattern_models: dict[str, type[AutoReflectionModel]] = {}
        self.dbs_reflected = set()

        self.schema = Schema(registry=self)
        # when setting a Model or Reflected Model execute the callbacks
        # Note: they are only executed if the Model is not in Registry yet
        self._onetime_callbacks: dict[
            Union[str, None], list[Callable[[type[BaseModelType]], None]]
        ] = defaultdict(list)
        self._callbacks: dict[Union[str, None], list[Callable[[type[BaseModelType]], None]]] = (
            defaultdict(list)
        )

        self.extra: dict[str, Database] = {
            k: v if isinstance(v, Database) else Database(v) for k, v in extra.items()
        }
        # we want to get all problems before failing
        assert all(
            [self.extra_name_check(x) for x in self.extra]  # noqa: C419
        ), "Invalid name in extra detected. See logs for details."
        self.metadata_by_url = MetaDataByUrlDict(registry=self)

        if with_content_type is not False:
            self._set_content_type(with_content_type)

    async def apply_default_force_nullable_fields(
        self,
        *,
        force_fields_nullable: Optional[Iterable[tuple[str, str]]] = None,
        model_defaults: Optional[dict[str, dict[str, Any]]] = None,
        filter_db_url: Optional[str] = None,
        filter_db_name: Union[str, None] = None,
    ) -> None:
        """For online migrations and after migrations to apply defaults."""
        if force_fields_nullable is None:
            force_fields_nullable = set(FORCE_FIELDS_NULLABLE.get())
        else:
            force_fields_nullable = set(force_fields_nullable)
        if model_defaults is None:
            model_defaults = {}
        for model_name, defaults in model_defaults.items():
            for default_name in defaults:
                force_fields_nullable.add((model_name, default_name))
        # for empty model names extract all matching models
        for item in list(force_fields_nullable):
            if not item[0]:
                force_fields_nullable.discard(item)
                for model in self.models.values():
                    if item[1] in model.meta.fields:
                        force_fields_nullable.add((model.__name__, item[1]))

        if not force_fields_nullable:
            return
        if isinstance(filter_db_name, str):
            if filter_db_name:
                filter_db_url = str(self.extra[filter_db_name].url)
            else:
                filter_db_url = str(self.database.url)
        models_with_fields: dict[str, set[str]] = {}
        for item in force_fields_nullable:
            if item[0] not in self.models:
                continue
            if item[1] not in self.models[item[0]].meta.fields:
                continue
            if not self.models[item[0]].meta.fields[item[1]].has_default():
                overwrite_default = model_defaults.get(item[0]) or {}
                if item[1] not in overwrite_default:
                    continue
            field_set = models_with_fields.setdefault(item[0], set())
            field_set.add(item[1])
        if not models_with_fields:
            return
        ops = []
        for model_name, field_set in models_with_fields.items():
            model = self.models[model_name]
            if filter_db_url and str(model.database.url) != filter_db_url:
                continue
            model_specific_defaults = model_defaults.get(model_name) or {}
            filter_kwargs = dict.fromkeys(field_set)

            async def wrapper_fn(
                _model: type["BaseModelType"] = model,
                _model_specific_defaults: dict = model_specific_defaults,
                _filter_kwargs: dict = filter_kwargs,
                _field_set: set[str] = field_set,
            ) -> None:
                # To reduce the memory usage, only retrieve pknames and load per object
                # We need to load all at once because otherwise the cursor could interfere with updates
                for obj in await _model.query.filter(**_filter_kwargs).only(*_model.pknames):
                    await obj.load()
                    kwargs = {
                        k: v for k, v in obj.extract_db_fields().items() if k not in _field_set
                    }
                    kwargs.update(_model_specific_defaults)
                    # We need to serialize per table because otherwise transactions can fail
                    # because of interlocking errors.
                    # Also the tables can get big
                    # is_partial = False
                    await obj._update(
                        False,
                        kwargs,
                        pre_fn=partial(
                            _model.meta.signals.pre_update.send_async,
                            is_update=True,
                            is_migration=True,
                        ),
                        post_fn=partial(
                            _model.meta.signals.post_update.send_async,
                            is_update=True,
                            is_migration=True,
                        ),
                    )

            ops.append(wrapper_fn())
        await asyncio.gather(*ops)

    def extra_name_check(self, name: Any) -> bool:
        if not isinstance(name, str):
            logger.error(f"Extra database name: {name!r} is not a string.")
            return False
        elif not name.strip():
            logger.error(f'Extra database name: "{name}" is empty.')
            return False

        if name.strip() != name:
            logger.warning(
                f'Extra database name: "{name}" starts or ends with whitespace characters.'
            )
        return True

    def __copy__(self) -> "Registry":
        content_type: Union[bool, type[BaseModelType]] = False
        if self.content_type is not None:
            try:
                content_type = self.get_model(
                    "ContentType", include_content_type_attr=False
                ).copy_edgy_model()
            except LookupError:
                content_type = self.content_type
        _copy = Registry(
            self.database, with_content_type=content_type, schema=self.db_schema, extra=self.extra
        )
        for registry_type in self.model_registry_types:
            dict_models = getattr(_copy, registry_type)
            dict_models.update(
                (
                    (
                        key,
                        val.copy_edgy_model(registry=_copy),
                    )
                    for key, val in getattr(self, registry_type).items()
                    if not val.meta.no_copy and key not in dict_models
                )
            )
        _copy.dbs_reflected = set(self.dbs_reflected)
        return _copy

    def _set_content_type(
        self,
        with_content_type: Union[Literal[True], type["BaseModelType"]],
        old_content_type_to_replace: Optional[type["BaseModelType"]] = None,
    ) -> None:
        from edgy.contrib.contenttypes.fields import BaseContentTypeField, ContentTypeField
        from edgy.contrib.contenttypes.models import ContentType
        from edgy.core.db.models.metaclasses import MetaInfo
        from edgy.core.db.relationships.related_field import RelatedField
        from edgy.core.utils.models import create_edgy_model

        if with_content_type is True:
            with_content_type = ContentType

        real_content_type: type[BaseModelType] = with_content_type

        if real_content_type.meta.abstract:
            meta_args = {
                "tablename": "contenttypes",
                "registry": self,
            }

            new_meta: MetaInfo = MetaInfo(None, **meta_args)
            # model adds itself to registry and executes callbacks
            real_content_type = create_edgy_model(
                "ContentType",
                with_content_type.__module__,
                __metadata__=new_meta,
                __bases__=(with_content_type,),
            )
        elif real_content_type.meta.registry is None:
            real_content_type.add_to_registry(self, name="ContentType")
        self.content_type = real_content_type

        def callback(model_class: type["BaseModelType"]) -> None:
            # they are not updated, despite this shouldn't happen anyway
            if issubclass(model_class, ContentType):
                return
            # skip if is explicit set or remove when copying
            for field in model_class.meta.fields.values():
                if isinstance(field, BaseContentTypeField):
                    if (
                        old_content_type_to_replace is not None
                        and field.target is old_content_type_to_replace
                    ):
                        field.target_registry = self
                        field.target = real_content_type
                        # simply overwrite
                        real_content_type.meta.fields[field.related_name] = RelatedField(
                            name=field.related_name,
                            foreign_key_name=field.name,
                            related_from=model_class,
                            owner=real_content_type,
                        )
                    return

            # e.g. exclude field
            if "content_type" in model_class.meta.fields:
                return
            related_name = f"reverse_{model_class.__name__.lower()}"
            assert related_name not in real_content_type.meta.fields, (
                f"duplicate model name: {model_class.__name__}"
            )

            field_args: dict[str, Any] = {
                "name": "content_type",
                "owner": model_class,
                "to": real_content_type,
                "no_constraint": real_content_type.no_constraint,
                "no_copy": True,
            }
            if model_class.meta.registry is not real_content_type.meta.registry:
                field_args["relation_has_post_delete_callback"] = True
                field_args["force_cascade_deletion_relation"] = True
            model_class.meta.fields["content_type"] = cast(
                "BaseFieldType",
                ContentTypeField(**field_args),
            )
            real_content_type.meta.fields[related_name] = RelatedField(
                name=related_name,
                foreign_key_name="content_type",
                related_from=model_class,
                owner=real_content_type,
            )

        self.register_callback(None, callback, one_time=False)

    @property
    def metadata_by_name(self) -> MetaDataDict:
        if getattr(self, "_metadata_by_name", None) is None:
            self._metadata_by_name = MetaDataDict(registry=self)
        return self._metadata_by_name

    @metadata_by_name.setter
    def metadata_by_name(self, value: MetaDataDict) -> None:
        metadata_dict = self.metadata_by_name
        metadata_dict.clear()
        for k, v in value.items():
            metadata_dict[k] = v
        self.metadata_by_url.process()

    @property
    def metadata(self) -> sqlalchemy.MetaData:
        warnings.warn(
            "metadata is deprecated use metadata_by_name or metadata_by_url instead",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.metadata_by_name[None]

    def get_model(
        self,
        model_name: str,
        *,
        include_content_type_attr: bool = True,
        exclude: Container[str] = (),
    ) -> type["BaseModelType"]:
        if (
            include_content_type_attr
            and model_name == "ContentType"
            and self.content_type is not None
        ):
            return self.content_type
        for model_dict_name in self.model_registry_types:
            if model_dict_name in exclude:
                continue
            model_dict: dict = getattr(self, model_dict_name)
            if model_name in model_dict:
                return cast(type["BaseModelType"], model_dict[model_name])
        raise LookupError(f'Registry doesn\'t have a "{model_name}" model.') from None

    def delete_model(self, model_name: str) -> bool:
        for model_dict_name in self.model_registry_types:
            model_dict: dict = getattr(self, model_dict_name)
            if model_name in model_dict:
                del model_dict[model_name]
                return True
        return False

    def refresh_metadata(
        self,
        *,
        update_only: bool = False,
        multi_schema: Union[bool, re.Pattern, str] = False,
        ignore_schema_pattern: Union[None, "re.Pattern", str] = "information_schema",
    ) -> None:
        if not update_only:
            for val in self.metadata_by_name.values():
                val.clear()
        maindatabase_url = str(self.database.url)
        if multi_schema is not False:
            schemes_tree: dict[str, tuple[Optional[str], list[str]]] = {
                v[0]: (key, v[2])
                for key, v in run_sync(self.schema.get_schemes_tree(no_reflect=True)).items()
            }
        else:
            schemes_tree = {
                maindatabase_url: (None, [self.db_schema]),
                **{str(v.url): (k, [None]) for k, v in self.extra.items()},
            }

        if isinstance(multi_schema, str):
            multi_schema = re.compile(multi_schema)
        if isinstance(ignore_schema_pattern, str):
            ignore_schema_pattern = re.compile(ignore_schema_pattern)
        for model_class in self.models.values():
            if not update_only:
                model_class._table = None
                model_class._db_schemas = {}
            url = str(model_class.database.url)
            if url in schemes_tree:
                extra_key, schemes = schemes_tree[url]
                for schema in schemes:
                    if multi_schema is not False:
                        if multi_schema is not True and multi_schema.match(schema) is None:
                            continue
                        if (
                            ignore_schema_pattern is not None
                            and ignore_schema_pattern.match(schema) is not None
                        ):
                            continue
                        if not getattr(model_class.meta, "is_tenant", False):
                            if (
                                model_class.__using_schema__ is Undefined
                                or model_class.__using_schema__ is None
                            ):
                                if schema != "":
                                    continue
                            elif model_class.__using_schema__ != schema:
                                continue
                    model_class.table_schema(schema=schema, metadata=self.metadata_by_url[url])

        # don't initialize to keep the metadata clean
        if not update_only:
            for model_class in self.reflected.values():
                model_class._table = None
                model_class._db_schemas = {}

    def register_callback(
        self,
        name_or_class: Union[type["BaseModelType"], str, None],
        callback: Callable[[type["BaseModelType"]], None],
        one_time: Optional[bool] = None,
    ) -> None:
        if one_time is None:
            # True for model specific callbacks, False for general callbacks
            one_time = name_or_class is not None
        called: bool = False
        if name_or_class is None:
            for model in self.models.values():
                callback(model)
                called = True
            for model in self.reflected.values():
                callback(model)
                called = True
            for name, model in self.tenant_models.items():
                # for tenant only models
                if name not in self.models:
                    callback(model)
                    called = True
        elif not isinstance(name_or_class, str):
            callback(name_or_class)
            called = True
        else:
            model_class = None
            with contextlib.suppress(LookupError):
                model_class = self.get_model(name_or_class)
            if model_class is not None:
                callback(model_class)
                called = True
        if name_or_class is not None and not isinstance(name_or_class, str):
            name_or_class = name_or_class.__name__
        if called and one_time:
            return
        if one_time:
            self._onetime_callbacks[name_or_class].append(callback)
        else:
            self._callbacks[name_or_class].append(callback)

    def execute_model_callbacks(self, model_class: type["BaseModelType"]) -> None:
        name = model_class.__name__
        callbacks = self._onetime_callbacks.get(name)
        while callbacks:
            callbacks.pop()(model_class)

        callbacks = self._onetime_callbacks.get(None)
        while callbacks:
            callbacks.pop()(model_class)

        callbacks = self._callbacks.get(name)
        if callbacks:
            for callback in callbacks:
                callback(model_class)

        callbacks = self._callbacks.get(None)
        if callbacks:
            for callback in callbacks:
                callback(model_class)

    @cached_property
    def declarative_base(self) -> Any:
        if self.db_schema:
            metadata = sqlalchemy.MetaData(schema=self.db_schema)
        else:
            metadata = sqlalchemy.MetaData()
        return sa_declarative_base(metadata=metadata)

    @property
    def engine(self) -> AsyncEngine:
        assert self.database.is_connected and self.database.engine, "database not initialized"
        return self.database.engine

    @property
    def sync_engine(self) -> Engine:
        return self.engine.sync_engine

    def init_models(
        self, *, init_column_mappers: bool = True, init_class_attrs: bool = True
    ) -> None:
        """
        Initializes lazy parts of models meta. Normally not needed to call.
        """
        for model_class in self.models.values():
            model_class.meta.full_init(
                init_column_mappers=init_column_mappers, init_class_attrs=init_class_attrs
            )

        for model_class in self.reflected.values():
            model_class.meta.full_init(
                init_column_mappers=init_column_mappers, init_class_attrs=init_class_attrs
            )

    def invalidate_models(self, *, clear_class_attrs: bool = True) -> None:
        """
        Invalidate all lazy parts of meta. They will automatically re-initialized on access.
        """
        for model_class in self.models.values():
            model_class.meta.invalidate(clear_class_attrs=clear_class_attrs)
        for model_class in self.reflected.values():
            model_class.meta.invalidate(clear_class_attrs=clear_class_attrs)

    def get_tablenames(self) -> set[str]:
        return_set = set()
        for model_class in self.models.values():
            return_set.add(model_class.meta.tablename)
        for model_class in self.reflected.values():
            return_set.add(model_class.meta.tablename)
        return return_set

    def _automigrate_update(
        self,
        migration_settings: "EdgySettings",
    ) -> None:
        from edgy import Instance, monkay
        from edgy.cli.base import upgrade

        with (
            monkay.with_extensions({}),
            monkay.with_settings(migration_settings),
            monkay.with_instance(Instance(registry=self), apply_extensions=False),
        ):
            self._is_automigrated = True
            monkay.evaluate_settings()
            monkay.apply_extensions()
            upgrade()

    async def _automigrate(self) -> None:
        from edgy import monkay

        migration_settings = self._automigrate_config
        if migration_settings is None or not monkay.settings.allow_automigrations:
            self._is_automigrated = True
            return

        await asyncio.to_thread(self._automigrate_update, migration_settings)

    async def _connect_and_init(self, name: Union[str, None], database: "Database") -> None:
        from edgy.core.db.models.metaclasses import MetaInfo

        await database.connect()
        if not self._is_automigrated:
            await self._automigrate()
        if not self.pattern_models or name in self.dbs_reflected:
            return
        schemes = set()
        for pattern_model in self.pattern_models.values():
            if name not in pattern_model.meta.databases:
                continue
            schemes.update(pattern_model.meta.schemes)
        tmp_metadata = sqlalchemy.MetaData()
        for schema in schemes:
            await database.run_sync(tmp_metadata.reflect, schema=schema)
        try:
            for table in tmp_metadata.tables.values():
                for pattern_model in self.pattern_models.values():
                    if name not in pattern_model.meta.databases or table.schema not in schemes:
                        continue
                    assert pattern_model.meta.model is pattern_model
                    # table.key would contain the schema name
                    if not pattern_model.meta.include_pattern.match(table.name) or (
                        pattern_model.meta.exclude_pattern
                        and pattern_model.meta.exclude_pattern.match(table.name)
                    ):
                        continue
                    if pattern_model.fields_not_supported_by_table(table):
                        continue
                    new_name = pattern_model.meta.template(table)
                    old_model: Optional[type[BaseModelType]] = None
                    with contextlib.suppress(LookupError):
                        old_model = self.get_model(
                            new_name, include_content_type_attr=False, exclude=("pattern_models",)
                        )
                    if old_model is not None:
                        raise Exception(
                            f"Conflicting model: {old_model.__name__} with pattern model: {pattern_model.__name__}"
                        )
                    concrete_reflect_model = pattern_model.copy_edgy_model(
                        name=new_name, meta_info_class=MetaInfo
                    )
                    concrete_reflect_model.meta.no_copy = True
                    concrete_reflect_model.meta.tablename = table.name
                    concrete_reflect_model.__using_schema__ = table.schema
                    concrete_reflect_model.add_to_registry(self, database=database)

            self.dbs_reflected.add(name)
        except BaseException as exc:
            await database.disconnect()
            raise exc

    async def __aenter__(self) -> "Registry":
        dbs: list[tuple[Union[str, None], Database]] = [(None, self.database)]
        for name, db in self.extra.items():
            dbs.append((name, db))
        ops = [self._connect_and_init(name, db) for name, db in dbs]
        results: list[Union[BaseException, bool]] = await asyncio.gather(
            *ops, return_exceptions=True
        )
        if any(isinstance(x, BaseException) for x in results):
            ops2 = []
            for num, value in enumerate(results):
                if not isinstance(value, BaseException):
                    ops2.append(dbs[num][1].disconnect())
                else:
                    logger.opt(exception=value).error("Failed to connect database.")
            await asyncio.gather(*ops2)
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]] = None,
        exc_value: Optional[BaseException] = None,
        traceback: Optional[TracebackType] = None,
    ) -> None:
        ops = [self.database.disconnect()]
        for value in self.extra.values():
            ops.append(value.disconnect())
        await asyncio.gather(*ops)

    @contextlib.contextmanager
    def with_async_env(
        self, loop: Optional[asyncio.AbstractEventLoop] = None
    ) -> Generator["Registry", None, None]:
        close: bool = False
        if loop is None:
            try:
                loop = asyncio.get_running_loop()
                # when in async context we don't create a loop
            except RuntimeError:
                # also when called recursively and current_eventloop is available
                loop = current_eventloop.get()
                if loop is None:
                    loop = asyncio.new_event_loop()
                    close = True

        token = current_eventloop.set(loop)
        try:
            yield run_sync(self.__aenter__(), loop=loop)
        finally:
            run_sync(self.__aexit__(), loop=loop)
            current_eventloop.reset(token)
            if close:
                loop.run_until_complete(loop.shutdown_asyncgens())
                loop.close()

    @overload
    def asgi(
        self,
        app: None,
        handle_lifespan: bool = False,
    ) -> Callable[[ASGIApp], ASGIHelper]: ...

    @overload
    def asgi(
        self,
        app: ASGIApp,
        handle_lifespan: bool = False,
    ) -> ASGIHelper: ...

    def asgi(
        self,
        app: Optional[ASGIApp] = None,
        handle_lifespan: bool = False,
    ) -> Union[ASGIHelper, Callable[[ASGIApp], ASGIHelper]]:
        """Return wrapper for asgi integration."""
        if app is not None:
            return ASGIHelper(app=app, registry=self, handle_lifespan=handle_lifespan)
        return partial(ASGIHelper, registry=self, handle_lifespan=handle_lifespan)

    async def create_all(
        self, refresh_metadata: bool = True, databases: Sequence[Union[str, None]] = (None,)
    ) -> None:
        # otherwise old references to non-existing tables, fks can lurk around
        if refresh_metadata:
            self.refresh_metadata(multi_schema=True)
        if self.db_schema:
            await self.schema.create_schema(
                self.db_schema, True, True, update_cache=True, databases=databases
            )
        else:
            # fallback when no schemes are in use. Because not all dbs support schemes
            # we cannot just use a scheme = ""
            for database in databases:
                db = self.database if database is None else self.extra[database]
                # don't warn here about inperformance
                async with db as db:
                    with db.force_rollback(False):
                        await db.create_all(self.metadata_by_name[database])

    async def drop_all(self, databases: Sequence[Union[str, None]] = (None,)) -> None:
        if self.db_schema:
            await self.schema.drop_schema(
                self.db_schema, cascade=True, if_exists=True, databases=databases
            )
        else:
            # fallback when no schemes are in use. Because not all dbs support schemes
            # we cannot just use a scheme = ""
            for database_name in databases:
                db = self.database if database_name is None else self.extra[database_name]
                # don't warn here about inperformance
                async with db as db:
                    with db.force_rollback(False):
                        await db.drop_all(self.metadata_by_name[database_name])


__all__ = ["Registry"]
