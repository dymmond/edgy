import asyncio
import contextlib
from collections.abc import Mapping, Sequence
from functools import cached_property, partial
from types import TracebackType
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Literal,
    Optional,
    Union,
    cast,
    overload,
)

import sqlalchemy
from loguru import logger
from sqlalchemy import Engine
from sqlalchemy.ext.asyncio.engine import AsyncEngine
from sqlalchemy.orm import declarative_base as sa_declarative_base

from edgy.core.connection.database import Database, DatabaseURL
from edgy.core.connection.schemas import Schema

from .asgi import ASGIApp, ASGIHelper

if TYPE_CHECKING:
    from edgy.contrib.autoreflection.models import AutoReflectionModel
    from edgy.core.db.fields.types import BaseFieldType
    from edgy.core.db.models.types import BaseModelType


class Registry:
    """
    The command center for the models of Edgy.
    """

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
        **kwargs: Any,
    ) -> None:
        self.db_schema = schema
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
        ] = {}
        self._callbacks: dict[Union[str, None], list[Callable[[type[BaseModelType]], None]]] = {}

        self.extra: Mapping[str, Database] = {
            k: v if isinstance(v, Database) else Database(v) for k, v in extra.items()
        }

        if with_content_type is not False:
            self._set_content_type(with_content_type)

    @property
    def metadata(self) -> sqlalchemy.MetaData:
        if not hasattr(self, "_metadata"):
            self._metadata = sqlalchemy.MetaData()
            self.refresh_metadata()
        return self._metadata

    @metadata.setter
    def metadata(self, value: sqlalchemy.MetaData) -> None:
        self._metadata = value

    def __copy__(self) -> "Registry":
        _copy = Registry(self.database)
        _copy.extra = self.extra
        _copy.models = {key: val.copy_edgy_model(_copy) for key, val in self.models.items()}
        _copy.reflected = {key: val.copy_edgy_model(_copy) for key, val in self.reflected.items()}
        _copy.tenant_models = {
            key: val.copy_edgy_model(_copy) for key, val in self.tenant_models.items()
        }
        _copy.pattern_models = {
            key: val.copy_edgy_model(_copy) for key, val in self.pattern_models.items()
        }
        _copy.dbs_reflected = set(self.dbs_reflected)
        if self.content_type is not None:
            try:
                _copy.content_type = self.get_model("ContentType")
            except LookupError:
                _copy.content_type = self.content_type
            # init callbacks
            _copy._set_content_type(_copy.content_type)
        return _copy

    def _set_content_type(
        self, with_content_type: Union[Literal[True], type["BaseModelType"]]
    ) -> None:
        from edgy.contrib.contenttypes.fields import BaseContentTypeFieldField, ContentTypeField
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
            real_content_type.add_to_registry(self, "ContentType")
        self.content_type = real_content_type

        def callback(model_class: type["BaseModelType"]) -> None:
            # they are not updated, despite this shouldn't happen anyway
            if issubclass(model_class, ContentType):
                return
            # skip if is explicit set
            for field in model_class.meta.fields.values():
                if isinstance(field, BaseContentTypeFieldField):
                    return
            # e.g. exclude field
            if "content_type" not in model_class.meta.fields:
                related_name = f"reverse_{model_class.__name__.lower()}"
                assert (
                    related_name not in real_content_type.meta.fields
                ), f"duplicate model name: {model_class.__name__}"
                model_class.meta.fields["content_type"] = cast(
                    "BaseFieldType",
                    ContentTypeField(
                        name="content_type",
                        owner=model_class,
                        to=real_content_type,
                        no_constraint=real_content_type.no_constraint,
                    ),
                )
                real_content_type.meta.fields[related_name] = RelatedField(
                    name=related_name,
                    foreign_key_name="content_type",
                    related_from=model_class,
                    owner=real_content_type,
                )

        self.register_callback(None, callback, one_time=False)

    def get_model(self, model_name: str) -> type["BaseModelType"]:
        if model_name in self.models:
            return self.models[model_name]
        elif model_name in self.reflected:
            return self.reflected[model_name]
        elif model_name in self.tenant_models:
            return self.tenant_models[model_name]
        else:
            raise LookupError(f"Registry doesn't have a {model_name} model.") from None

    def refresh_metadata(self) -> None:
        self.metadata.clear()
        for model_class in self.models.values():
            model_class._table = None
            model_class._db_schemas = {}
            model_class.table_schema(schema=self.db_schema)

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
            self._onetime_callbacks.setdefault(name_or_class, []).append(callback)
        else:
            self._callbacks.setdefault(name_or_class, []).append(callback)

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

    async def _connect_and_init(self, name: Union[str, None], database: "Database") -> None:
        from edgy.core.db.models.metaclasses import MetaInfo

        await database.connect()
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
                        old_model = self.get_model(new_name)
                    if old_model is not None:
                        raise Exception(
                            f"Conflicting model: {old_model.__name__} with pattern model: {pattern_model.__name__}"
                        )
                    concrete_reflect_model = pattern_model.copy_edgy_model(
                        name=new_name, meta_info_class=MetaInfo
                    )
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
            self.refresh_metadata()
        if self.db_schema:
            await self.schema.create_schema(
                self.db_schema, True, True, update_cache=True, databases=databases
            )
        else:
            for database in databases:
                db = self.database if database is None else self.extra[database]
                # don't warn here about inperformance
                async with db as db:
                    with db.force_rollback(False):
                        await db.create_all(self.metadata)

    async def drop_all(self, databases: Sequence[Union[str, None]] = (None,)) -> None:
        if self.db_schema:
            await self.schema.drop_schema(self.db_schema, True, True, databases=databases)
        else:
            for database in databases:
                db = self.database if database is None else self.extra[database]
                # don't warn here about inperformance
                async with db as db:
                    with db.force_rollback(False):
                        await db.drop_all(self.metadata)
