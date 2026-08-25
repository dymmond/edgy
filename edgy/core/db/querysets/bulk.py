from __future__ import annotations

import asyncio
from collections.abc import (
    Awaitable,
    Collection,
    Hashable,
    Iterable,
)
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Generic, cast

import orjson
import sqlalchemy
from sqlalchemy.exc import IntegrityError

from edgy.core.db.context_vars import CURRENT_INSTANCE
from edgy.core.utils.concurrency import run_concurrently
from edgy.core.utils.db import check_db_connection
from edgy.exceptions import QuerySetError, SkipOperation

from .types import (
    EdgyEmbedTarget,
    EdgyModel,
)

if TYPE_CHECKING:  # pragma: no cover
    from databasez.core.connection import Connection

    from edgy.core.db.models.types import BaseModelType
    from edgy.core.db.querysets.queryset import QuerySet

_empty_set = cast(set[Any], frozenset())


def _getter_dict(obj: Any, key: str) -> Any:
    return obj[key]


def _extract_unique_lookup_key(
    obj: Any, unique_fields: Iterable[str], *, no_load: bool = False, allow_none: bool = False
) -> tuple | None:
    """
    Extracts a unique lookup key from an object or dictionary.
    (Helper function, stays in base)
    """
    if obj is None:
        return None
    lookup_key = []
    if isinstance(obj, dict):
        _getter: Any = _getter_dict
    elif no_load:
        _getter = object.__getattribute__
    else:
        _getter = getattr
    for _field in unique_fields:
        try:
            value = _getter(obj, _field)
        except (KeyError, AttributeError):
            return None
        if not allow_none and value is None:
            # None is never unique except for retrieval
            return None
        if hasattr(value, "create_model_key"):
            try:
                value = value.create_model_key()
            except AttributeError:
                return None
        elif isinstance(value, dict | list):
            value = orjson.dumps(value, option=orjson.OPT_SORT_KEYS)
        if not isinstance(value, Hashable):
            return None
        lookup_key.append(value)
    return tuple(lookup_key)


@dataclass(kw_only=True)
class BulkOperation(Generic[EdgyModel, EdgyEmbedTarget]):
    """
    Bulk gets, updates or creates records in a table.

    If records exist based on unique fields, they are retrieved.
    Otherwise, new records are created.

    Kwargs:
        unique_fields (Collection[str]): Explicit set fields or columns that determine uniqueness.
        unique_columns (Collection[str]): Resolved columns that determine uniqueness.
        update_fields (set[str]): Fields which are updated.
        create (bool): Create objects.
        update (bool): Update retrieved objects or generate updates.
        retrieve (bool): Retrieve objects. Otherwise update only path.
        signal_postfix (str | None): Send signal. None to disable.
        ignore_create_conflicts (bool): Ignore conflicting entries on insert.
        none_on_existing (bool): When in existing and a collision was found return None instead.
        used_instance (BaseModelType | QuerySet | None): Use this value as instance.
    """

    owner: QuerySet[EdgyModel, EdgyEmbedTarget]
    resolve_embed: bool
    create: bool
    update: bool
    retrieve: bool
    unique_columns: Collection[str]
    unique_fields: Collection[str] = _empty_set
    update_fields: set[str] = _empty_set
    signal_postfix: str | None = None
    signal_params: dict[str, Any] = field(default_factory=dict)
    signal_models: None | Iterable[type[BaseModelType]] = None
    ignore_create_conflicts: bool = False
    none_on_existing: bool = False
    used_instance: BaseModelType | QuerySet = field(default=cast(Any, None))
    row_count_create: int | None = field(init=False, default=0)
    row_count_update: int | None = field(init=False, default=0)
    create_params: list[tuple[EdgyModel, int, set[str]]] = field(init=False, default_factory=list)
    update_params: list[tuple[EdgyModel, int, set[str]]] = field(init=False, default_factory=list)
    skip_post_save: set[int] = field(init=False, default_factory=set)
    model_class: type[EdgyModel] = field(init=False)
    proxy_model_class: type[EdgyModel] = field(init=False)
    instances_and_created: list[tuple[EdgyModel | None, bool]] = field(
        init=False, default_factory=list
    )
    result: list[tuple[EdgyModel | None, bool]] | list[tuple[EdgyEmbedTarget | None, bool]] = (
        field(init=False, default_factory=list)
    )
    existing_records: dict[tuple, EdgyModel] = field(init=False, default_factory=dict)
    execution_step: int = field(default=0, init=False)
    provided_signal_params: dict = field(init=False)

    def __post_init__(self) -> None:
        if cast(Any, self.used_instance) is None:
            self.used_instance = self.owner
        self.model_class = self.owner.model_class
        self.proxy_model_class = cast(type[EdgyModel], self.model_class.proxy_model)
        self.provided_signal_params = self.signal_params
        # we can edit the signals now
        self.signal_params = {}
        if self.signal_models is None:
            self.signal_models = [self.model_class]
        else:
            self.signal_models = [*self.signal_models]

    async def prepare(self, objs: Iterable[dict[str, Any] | EdgyModel]) -> None:
        """
        Prepares objects and retrieve. No modifying database operations are executed yet.
        This method also initializes `signal_params` for execution with `apply_db`.

        Args:
            objs (Iterable[Union[dict[str, Any], EdgyModel]]): A list of objects or dictionaries.
        """
        if self.execution_step >= 1:
            raise Exception("Was already executed")
        self.execution_step = 1

        concurrent_limit = 1 if getattr(self.owner.database, "force_rollback", False) else None

        def _add_create_obj(
            obj: EdgyModel | dict,
            pos: int,
        ) -> tuple[EdgyModel | None, bool]:
            lookup_key = _extract_unique_lookup_key(
                obj, self.unique_fields or self.unique_columns, no_load=not self.unique_fields
            )
            if lookup_key and lookup_key in self.existing_records:
                return (
                    None if self.none_on_existing else self.existing_records[lookup_key],
                    False,
                )
            created: EdgyModel
            if isinstance(obj, dict):
                created = self.model_class(
                    **{k: v for k, v in obj.items() if k in self.model_class.meta.fields}
                )
                self.create_params.append((created, pos, set(obj.keys())))
            else:
                created = obj
                self.create_params.append((created, pos, set(obj.meta.fields.keys())))
            if lookup_key:
                self.existing_records[lookup_key] = created
            return created, True

        if self.retrieve:
            # IMPROVEMENT TODO: move query part into a transaction and issue at best just one database query
            free_unique_columns: set[str] = {
                colname
                for colname in self.unique_columns
                if colname not in self.model_class.meta.columns_to_field
            }

            if self.unique_columns:

                async def _iterate_retrieve(
                    obj: EdgyModel | dict, pos: int
                ) -> tuple[EdgyModel | None, bool]:
                    if not isinstance(obj, (self.model_class, self.proxy_model_class, dict)):
                        raise ValueError(
                            f"Instance provided of wrong type: `{type(obj)!r}` required: `{self.model_class!r}`."
                        )
                    # try deduplicating before issuing a db query
                    lookup_key_precheck = (
                        None
                        if self.update
                        else _extract_unique_lookup_key(
                            obj,
                            self.unique_fields or self.unique_columns,
                            no_load=True,
                            # for retrieval okay
                            allow_none=True,
                        )
                    )
                    if lookup_key_precheck and lookup_key_precheck in self.existing_records:
                        return self.existing_records[lookup_key_precheck], False
                    filter_kwargs = {}
                    dict_fields = {}
                    incomplete = False
                    if isinstance(obj, dict):
                        for field in self.unique_fields:
                            if field not in obj:
                                incomplete = True
                            else:
                                value = obj[field]
                                if isinstance(value, dict):
                                    dict_fields[field] = value
                                else:
                                    filter_kwargs[field] = value
                        for column in free_unique_columns:
                            if column not in obj:
                                incomplete = True
                            else:
                                value = obj[column]
                                assert not isinstance(value, dict)
                                filter_kwargs[column] = value
                    else:
                        for field in self.unique_fields:
                            if not hasattr(obj, field):
                                incomplete = True
                            else:
                                value = getattr(obj, field)
                                if isinstance(value, dict):
                                    dict_fields[field] = value
                                else:
                                    filter_kwargs[field] = value
                        for column in free_unique_columns:
                            if not hasattr(obj, column):
                                incomplete = True
                            else:
                                value = getattr(obj, column)
                                assert not isinstance(value, dict)
                                filter_kwargs[column] = value

                    found_obj: EdgyModel | None = None
                    # prevent queries with user selected unique_fields/columns
                    if not incomplete:
                        # Using an array fixed an edgy-guardian bug when using databasez.iterate indirectly and
                        # is safe in case force_rollback is active
                        # Models can also issue loads by accessing attrs for building unique_fields
                        # For limiting use something like QuerySet.limit(100).bulk_get_or_create(...)
                        for instance in await self.owner.update_embed_parent(None).filter(
                            **filter_kwargs
                        ):
                            if all(
                                # compare dicts
                                getattr(instance, k) == expected
                                for k, expected in dict_fields.items()
                            ):
                                lookup_key = _extract_unique_lookup_key(
                                    instance,
                                    self.unique_fields or self.unique_columns,
                                    no_load=not self.unique_fields,
                                    # for retrieval okay
                                    allow_none=True,
                                )
                                assert lookup_key is not None, (
                                    "invalid fields/attributes in unique_fields"
                                )
                                if lookup_key:
                                    if lookup_key not in self.existing_records:
                                        found_obj = self.existing_records[lookup_key] = instance
                                    else:
                                        found_obj = self.existing_records[lookup_key]
                                else:
                                    found_obj = instance
                                break
                    if found_obj is not None:
                        if self.update:
                            if isinstance(obj, dict):
                                for key in self.update_fields:
                                    if key in obj:
                                        setattr(found_obj, key, obj[key])
                                self.update_params.append((found_obj, pos, set(obj.keys())))
                            else:
                                for key in self.update_fields:
                                    if hasattr(obj, key):
                                        setattr(found_obj, key, getattr(obj, key))
                                self.update_params.append(
                                    (found_obj, pos, set(obj.meta.fields.keys()))
                                )
                        return None if self.none_on_existing else found_obj, False
                    elif self.create:
                        return _add_create_obj(obj, pos)
                    else:
                        return None, False

                self.instances_and_created = await run_concurrently(
                    [_iterate_retrieve(obj, pos) for pos, obj in enumerate(objs)],
                    limit=concurrent_limit,
                )
        elif self.create:
            for pos, obj in enumerate(objs):
                self.instances_and_created.append(_add_create_obj(obj, pos))
        elif self.update:
            # update is last, if creation fails fallback to update
            for pos, obj in enumerate(objs):
                updated: EdgyModel
                if isinstance(obj, dict):
                    updated = self.proxy_model_class(**obj)
                else:
                    updated = obj
                    if not isinstance(updated, self.model_class | self.proxy_model_class):
                        raise ValueError(
                            f"Instance provided of wrong type: `{type(updated)!r}` required: `{self.model_class!r}`."
                        )
                if updated.can_load:
                    self.update_params.append(
                        (
                            updated,
                            pos,
                            set(obj.keys() if isinstance(obj, dict) else obj.meta.fields.keys()),
                        )
                    )
                    self.instances_and_created.append((updated, False))
                else:
                    self.instances_and_created.append((None, False))
        self.signal_params = {
            "instance": self.used_instance,
            "raw_values": self.instances_and_created,
            "create_params": self.create_params,
            "update_params": self.update_params,
            **self.provided_signal_params,
        }

    async def send_pre_signal(self) -> None:
        if self.execution_step >= 2:
            raise Exception("Was already executed")
        self.execution_step = 2
        ops = []
        seen_signals: set[int] = set()
        for model_class in self.signal_models:
            signal = getattr(model_class.meta.signals, f"pre_{self.signal_postfix}")
            if (signal_id := id(signal)) in seen_signals:
                continue
            seen_signals.add(signal_id)
            ops.append(
                signal.send_async(
                    self.model_class,
                    **self.signal_params,
                )
            )
        try:
            await asyncio.gather(*ops)
        except SkipOperation as exc:
            self.execution_step = 4  # cache
            self.signal_params["operation_skipped"] = True
            self.signal_params["values"] = None
            raise exc

    async def apply_db(self) -> None:
        """
        Modify the database.
        It resets the signal_params at the end of the method, so we can modify it again for `send_post_signal`.
        """
        if self.execution_step >= 3:
            raise Exception("Was already executed")
        self.execution_step = 3

        concurrent_limit = 1 if getattr(self.owner.database, "force_rollback", False) else None

        queryset: QuerySet[EdgyModel, EdgyEmbedTarget] = self.owner._clone()
        _unique_cols_and_update_fields: set = self.update_fields.union(self.unique_columns)
        _update_columns: set[str] = {
            col
            for field in self.update_fields
            for col in self.model_class.meta.field_to_column_names[field]
        }

        can_result_cache = not self.owner.embed_parent
        if self.resolve_embed and queryset.embed_parent:
            # check if all are elligable and can be resolved
            if not all(
                res[0] is None or res[0].can_load or res[1] for res in self.instances_and_created
            ):
                raise QuerySetError(
                    detail="Not all resulting objects are fully defined for loading and `resolve_embed=True`",
                )
            can_result_cache = True

        check_db_connection(queryset.database, 4)
        row_count_create_single = 0

        async def _iterate_create(
            item: tuple[EdgyModel, int, set[str]],
            connection: Connection,
            returning: list[sqlalchemy.ColumnElement],
        ) -> dict[str, Any] | None:
            nonlocal row_count_create_single
            original_field_values = item[0].extract_db_fields()
            col_values: dict[str, Any] = item[0].extract_column_values(
                original_field_values,
                phase="prepare_insert",
                instance=self.used_instance,
                model_instance=item[0],
            )
            if self.model_class.meta.pre_save_fields:
                col_values.update(
                    await item[0].execute_pre_save_hooks(
                        col_values, original_field_values, is_update=False
                    )
                )
            if self.ignore_create_conflicts or (
                self.resolve_embed and queryset.embed_parent and not item[0].can_load
            ):
                try:
                    cm = AsyncExitStack()
                    await cm.enter_async_context(connection)
                    await cm.enter_async_context(connection.transaction())
                    async with cm:
                        if returning:
                            expression: Any = (
                                queryset.table.insert().values(**col_values).returning(*returning)
                            )
                            returned_mapping = dict(
                                (await connection.fetch_one(expression))._mapping
                            )
                        else:
                            expression = queryset.table.insert().values(**col_values)
                            pk_values = await connection.execute(expression)
                            returned_mapping = (
                                dict(pk_values._mapping) if hasattr(pk_values, "_mapping") else {}
                            )
                        for col_name, col_key in self.model_class.meta.columns_remapping.items():
                            if col_name in returned_mapping:
                                returned_mapping[col_key] = returned_mapping.pop(col_name)
                        col_values.update(returned_mapping)

                        new_kwargs = self.model_class.transform_input(
                            col_values, phase="post_insert", instance=self, model_instance=item[0]
                        )
                        item[0].__dict__.update(new_kwargs)
                        row_count_create_single += 1
                except IntegrityError:
                    if not self.ignore_create_conflicts:
                        raise
                    if self.update and item[0].can_load:
                        # we can do an update, but not a retrieval because
                        # a retrieval doesn't overwrite the potential wrong values
                        # maybe still issue a load afterwards
                        # we need to be **sure** that the instance is loadable and copy the `identifying_db_fields`
                        # othewise we can end with an invalid proxy
                        proxy = self.proxy_model_class(
                            **item[0].extract_db_fields(_unique_cols_and_update_fields)
                        )
                        proxy.identifying_db_fields = item[0].identifying_db_fields
                        self.update_params.append((proxy, item[1], item[2]))
                        self.instances_and_created[item[1]] = (proxy, False)
                        self.skip_post_save.add(id(item[0]))
                    else:
                        # always return None because we don't know why it failed or we can't recover
                        self.instances_and_created[item[1]] = (None, False)
                        self.skip_post_save.add(id(item[0]))
                return None
            return col_values

        async def _iterate_update(obj: EdgyModel) -> dict[str, Any]:
            original_field_values = obj.extract_db_fields(_unique_cols_and_update_fields)
            # copied from update
            col_values: dict[str, Any] = self.model_class.extract_column_values(
                original_field_values,
                is_update=True,
                is_partial=True,
                phase="prepare_update",
                instance=self.used_instance,
                model_instance=obj,
            )
            if self.model_class.meta.pre_save_fields:
                col_values.update(
                    await obj.execute_pre_save_hooks(
                        col_values, original_field_values, is_update=True
                    )
                )
            if not _update_columns.issubset(col_values):
                raise QuerySetError(
                    detail=f"Missing columns: {_update_columns.difference(col_values)}. Check `update_fields` or the input values."
                )
            new_kwargs = self.model_class.transform_input(
                col_values, phase="post_update", instance=self, model_instance=obj
            )
            obj.__dict__.update(new_kwargs)
            return {f"__{item[0]}": item[1] for item in col_values.items()}

        token = CURRENT_INSTANCE.set(self.used_instance)
        try:
            async with (
                queryset.database as database,
                database.transaction(),
                database.connection() as connection,
            ):
                create_obj_values: list[dict | None] = []
                if self.create_params:
                    # we can't just use label. If the column.key has an invalid name for the db
                    # we would cause an foo AS invalid clause
                    returning: list[sqlalchemy.ColumnElement] = (
                        [
                            col
                            for col in queryset.table.columns.values()
                            if col.server_default is not None or col.autoincrement
                        ]
                        if database.engine.dialect.insert_returning
                        else []
                    )
                    create_obj_values = [
                        val
                        for val in (
                            await run_concurrently(
                                [
                                    # one connection, many transactions
                                    _iterate_create(
                                        tup,
                                        connection,
                                        returning,
                                    )
                                    for tup in self.create_params
                                ],
                                # must be serial, this is currently a hard requirement
                                # otherwise many to many fields fail under load
                                limit=1,
                            )
                        )
                        if val is not None
                    ]
                    # we need to recheck if the conditions are still valid
                    if create_obj_values:
                        expression_create = queryset.table.insert().values(create_obj_values)
                        async with connection.transaction():
                            create_return_result = cast(
                                None | int | list, await connection.execute_many(expression_create)
                            )
                        self.row_count_create = (
                            len(create_return_result)
                            if isinstance(create_return_result, list)
                            else create_return_result
                        )
                if self.row_count_create is not None:
                    self.row_count_create += row_count_create_single
                # prevent calling db with empty iterable, this causes errors
                if self.update_params:
                    update_obj_values = await run_concurrently(
                        [_iterate_update(item[0]) for item in self.update_params],
                        limit=concurrent_limit,
                    )
                    # by default pknames
                    unique_query_placeholder = (
                        queryset.table.columns[col]
                        == sqlalchemy.bindparam(
                            f"__{col}",
                            type_=queryset.table.columns[col].type,
                        )
                        for col in self.unique_columns
                    )
                    expression_update = queryset.table.update().where(*unique_query_placeholder)
                    values_placeholder: dict[str, Any] = {
                        col: sqlalchemy.bindparam(
                            f"__{col}", type_=queryset.table.columns[col].type
                        )
                        for col in _update_columns
                    }
                    expression_update = expression_update.values(values_placeholder)

                    async with connection.transaction():
                        update_result_return = cast(
                            None | int | list,
                            await connection.execute_many(expression_update, update_obj_values),
                        )
                    self.row_count_update = (
                        len(update_result_return)
                        if isinstance(update_result_return, list)
                        else update_result_return
                    )

                if self.update_params or self.create_params:
                    # only the results change
                    self.owner._clear_cache(
                        keep_cached_selected=True,
                        keep_result_cache=can_result_cache,
                    )
                    operations: list[Awaitable] = []
                    if self.model_class.meta.post_save_fields:
                        operations.extend(
                            tup[0].execute_post_save_hooks(tup[2], is_update=False)
                            # otherwise we would execute twice or one time for non-existing rows
                            for tup in self.create_params
                            if id(tup[0]) not in self.skip_post_save
                        )
                        if not self.model_class.meta.post_save_fields.isdisjoint(
                            self.update_fields
                        ):
                            operations.extend(
                                tup[0].execute_post_save_hooks(self.update_fields, is_update=True)
                                for tup in self.update_params
                                # we currently doesn't put update_objs in skip_post_save
                            )
                    if operations:
                        await run_concurrently(
                            operations,
                            limit=concurrent_limit,
                        )
        finally:
            CURRENT_INSTANCE.reset(token)
        if queryset.embed_parent and self.resolve_embed:
            immediate = await run_concurrently(
                [queryset._embed_parent_in_result(tup[0]) for tup in self.instances_and_created],
                limit=concurrent_limit,
            )
            self.result = list(
                zip(
                    [item[1] for item in immediate],
                    (res[1] for res in self.instances_and_created),
                    strict=True,
                )
            )
        else:
            self.result = self.instances_and_created
        # reinitialize
        self.signal_params = {
            "instance": self.used_instance,
            "raw_values": self.instances_and_created,
            "values": self.result,
            "create_params": self.create_params,
            "update_params": self.update_params,
            "operation_skipped": False,
            **self.provided_signal_params,
        }
        if self.create:
            self.signal_params["row_count_create"] = self.row_count_create
        if self.update:
            self.signal_params["row_count_update"] = self.row_count_update

    def update_cache(self) -> None:
        if self.execution_step >= 4:
            raise Exception("Was already executed")
        self.execution_step = 4
        if self.resolve_embed and self.owner.embed_parent:
            # embed can be None so only check None from instances if the entry really not exists
            immediate = [
                tup
                for tup in zip(
                    (res[0] for res in self.instances_and_created),
                    [item[0] for item in self.result],
                    strict=True,
                )
                if tup[0] is not None
            ]
            self.owner._cache.update(
                self.model_class,
                [item[1] for item in immediate],
                cache_keys=[
                    self.owner._cache.create_cache_key(self.model_class, item[0])
                    for item in immediate
                ],
            )
        elif not self.owner.embed_parent:
            self.owner._cache.update(
                self.model_class,
                [
                    tup[0]
                    for tup in self.instances_and_created
                    if tup[0] is not None and tup[0].can_load
                ],
                cache_keys=[
                    self.owner._cache.create_cache_key(self.model_class, tup[0])
                    for tup in self.instances_and_created
                    if tup[0] is not None and tup[0].can_load
                ],
            )

    async def send_post_signal(self) -> None:
        if self.execution_step >= 5:
            raise Exception("Was already executed")
        self.execution_step = 5
        ops = []
        seen_signals: set[int] = set()
        for model_class in self.signal_models:
            signal = getattr(model_class.meta.signals, f"post_{self.signal_postfix}")
            if (signal_id := id(signal)) in seen_signals:
                continue
            seen_signals.add(signal_id)
            ops.append(
                signal.send_async(
                    self.model_class,
                    **self.signal_params,
                )
            )
        await asyncio.gather(*ops)
