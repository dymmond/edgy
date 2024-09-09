from functools import cached_property
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Literal, Mapping, Type, Union, cast

import sqlalchemy
from sqlalchemy import Engine
from sqlalchemy.ext.asyncio.engine import AsyncEngine
from sqlalchemy.orm import declarative_base as sa_declarative_base

from edgy.core.connection.database import Database, DatabaseURL
from edgy.core.connection.schemas import Schema
from edgy.core.utils.models import create_edgy_model

if TYPE_CHECKING:
    from edgy.core.db.fields.types import BaseFieldType
    from edgy.core.db.models.types import BaseModelType


class Registry:
    """
    The command center for the models of Edgy.
    """

    db_schema: Union[str, None] = None
    content_type: Union[Type["BaseModelType"], None]

    def __init__(
        self,
        database: Union[Database, str, DatabaseURL],
        *,
        with_content_type: Union[bool, Type["BaseModelType"]] = False,
        **kwargs: Any,
    ) -> None:
        self.db_schema = kwargs.pop("schema", None)
        extra = kwargs.pop("extra", {})
        self.database: Database = (
            database if isinstance(database, Database) else Database(database, **kwargs)
        )
        self.models: Dict[str, Type[BaseModelType]] = {}
        self.reflected: Dict[str, Type[BaseModelType]] = {}
        self.tenant_models: Dict[str, Type[BaseModelType]] = {}
        # when setting a Model or Reflected Model execute the callbacks
        # Note: they are only executed if the Model is not in Registry yet
        self._onetime_callbacks: Dict[
            Union[str, None], List[Callable[[Type[BaseModelType]], None]]
        ] = {}
        self._callbacks: Dict[Union[str, None], List[Callable[[Type[BaseModelType]], None]]] = {}

        self.extra: Mapping[str, Database] = {
            k: v if isinstance(v, Database) else Database(v) for k, v in extra.items()
        }

        self.schema = Schema(registry=self)

        self._metadata: sqlalchemy.MetaData = (
            sqlalchemy.MetaData(schema=self.db_schema)
            if self.db_schema is not None
            else sqlalchemy.MetaData()
        )
        if with_content_type is not False:
            self._set_content_type(with_content_type)

    def _set_content_type(
        self, with_content_type: Union[Literal[True], Type["BaseModelType"]]
    ) -> None:
        from edgy.contrib.contenttypes.fields import BaseGenericForeignKeyField, GenericForeignKey
        from edgy.contrib.contenttypes.models import ContentType
        from edgy.core.db.models.metaclasses import MetaInfo
        from edgy.core.db.relationships.related_field import RelatedField

        if with_content_type is True:
            with_content_type = ContentType

        real_content_type: Type[BaseModelType] = with_content_type

        if real_content_type.meta.abstract:
            meta_args = {
                "tablename": "contenttypes",
                "registry": self,
            }

            new_meta: MetaInfo = MetaInfo(None, **meta_args)
            real_content_type = create_edgy_model(
                "ContentType",
                with_content_type.__module__,
                __metadata__=new_meta,
                __bases__=(with_content_type,),
            )
            self.models["ContentType"] = real_content_type
        self.content_type = real_content_type

        def callback(model_class: Type["BaseModelType"]) -> None:
            # they are not updated, despite this shouldn't happen anyway
            if issubclass(model_class, ContentType):
                return
            # skip if is explicit set
            for field in model_class.meta.fields.values():
                if isinstance(field, BaseGenericForeignKeyField):
                    return
            # e.g. exclude field
            if "content_type" not in model_class.meta.fields:
                related_name = f"reverse_{model_class.__name__.lower()}"
                assert (
                    related_name not in real_content_type.meta.fields
                ), f"duplicate model name: {model_class.__name__}"
                model_class.meta.fields["content_type"] = cast(
                    "BaseFieldType",
                    GenericForeignKey(
                        name="content_type", owner=model_class, to=real_content_type, registry=self
                    ),
                )
                real_content_type.fields[related_name] = RelatedField(
                    name=related_name,
                    foreign_key_name="content_type",
                    related_from=model_class,
                    owner=real_content_type,
                    registry=real_content_type.meta.registry,
                )
                if real_content_type.meta._is_init:
                    real_content_type.meta.post_save_fields.add(related_name)

        self.register_callback(None, callback, one_time=False)

    @property
    def metadata(self) -> Any:
        for model_class in self.models.values():
            model_class.table_schema(schema=self.db_schema)
        return self._metadata

    @metadata.setter
    def metadata(self, value: sqlalchemy.MetaData) -> None:
        self._metadata = value

    def register_callback(
        self,
        name_or_class: Union[Type["BaseModelType"], str, None],
        callback: Callable[[Type["BaseModelType"]], None],
        one_time: bool,
    ) -> None:
        if name_or_class is not None and not isinstance(name_or_class, str):
            name_or_class = name_or_class.__name__
        called: bool = False
        if name_or_class is None:
            for model in self.models.values():
                callback(model)
                called = True
            for model in self.reflected.values():
                callback(model)
                called = True
        else:
            if name_or_class in self.models:
                callback(self.models[name_or_class])
                called = True
            elif name_or_class in self.reflected:
                callback(self.reflected[name_or_class])
                called = True
        if called and one_time:
            return
        if one_time:
            self._onetime_callbacks.setdefault(name_or_class, []).append(callback)
        else:
            self._callbacks.setdefault(name_or_class, []).append(callback)

    def execute_model_callbacks(self, model_class: Type["BaseModelType"]) -> None:
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

    async def create_all(self) -> None:
        if self.db_schema:
            await self.schema.create_schema(self.db_schema, True)
        async with self.database as database:
            with database.force_rollback(False):
                await database.create_all(self.metadata)

    async def drop_all(self) -> None:
        if self.db_schema:
            await self.schema.drop_schema(self.db_schema, True, True)
        async with self.database as database:
            with database.force_rollback(False):
                await database.drop_all(self.metadata)
