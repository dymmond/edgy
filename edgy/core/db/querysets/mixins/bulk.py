from __future__ import annotations

import asyncio
import warnings
from collections.abc import (
    Awaitable,
    Collection,
    Iterable,
    Sequence,
)
from typing import TYPE_CHECKING, Any, Generic, cast

import orjson
import sqlalchemy
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError

from edgy.core.db.context_vars import CURRENT_INSTANCE
from edgy.core.utils.concurrency import run_concurrently
from edgy.core.utils.db import check_db_connection
from edgy.exceptions import QuerySetError

from ..types import (
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
    obj: Any, unique_fields: Iterable[str], *, no_load: bool = False
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
    for field in unique_fields:
        try:
            value = _getter(obj, field)
        except (KeyError, AttributeError):
            return None
        if isinstance(value, BaseModel):
            if not getattr(value, "can_load", False):
                return None
            value = orjson.dumps(
                value.model_dump(mode="json", include=value.pknames), option=orjson.OPT_SORT_KEYS
            )
        elif isinstance(value, dict | list):
            value = orjson.dumps(value, option=orjson.OPT_SORT_KEYS)
        lookup_key.append(value)
    return tuple(lookup_key)


class BulkMixin(Generic[EdgyModel]):
    model_class: type[EdgyModel]

    async def _bulk_get_update_or_create(
        self,
        *,
        objs: Iterable[dict[str, Any] | EdgyModel],
        resolve_embed: bool,
        unique_fields: Collection[str] = _empty_set,
        unique_columns: Collection[str],
        update_fields: set[str] = _empty_set,
        create: bool,
        update: bool,
        retrieve: bool,
        ignore_create_conflicts: bool = False,
        none_on_existing: bool = False,
        used_instance: BaseModelType | QuerySet | None = None,
    ) -> Sequence[tuple[EdgyModel | None, bool]] | Sequence[tuple[EdgyEmbedTarget | None, bool]]:
        """
        Bulk gets, updates or creates records in a table.

        If records exist based on unique fields, they are retrieved.
        Otherwise, new records are created.

        Kwargs:
            objs (Iterable[Union[dict[str, Any], EdgyModel]]): A list of objects or dictionaries.
            unique_fields (Collection[str]): Explicit set fields or columns that determine uniqueness.
            unique_columns (Collection[str]): Resolved columns that determine uniqueness.
            update_fields (set[str]): Fields which are updated.
            create (bool): Create objects.
            update (bool): Update retrieved objects or generate updates.
            retrieve (bool): Retrieve objects. Otherwise update only path.
            ignore_create_conflicts (bool): Ignore conflicting entries on insert.
            none_on_existing (bool): When in existing and a collision was found return None instead.
            used_instance (BaseModelType | QuerySet | None): Use this value as instance.

        Returns:
           Sequence[tuple[EdgyModel | None, bool]] | Sequence[tuple[EdgyEmbedTarget | None, bool]]:
               A list of retrieved or newly created objects. Second entry is True if instance was created.
        """
        queryset: QuerySet = self._clone()
        create_params: list[tuple[EdgyModel, int, set[str]]] = []
        update_objs: list[EdgyModel] = []
        skip_post_save: set[int] = set()
        used_instance = cast("QuerySet", self) if used_instance is None else used_instance

        returned_objs_with_created_with_null: list[tuple[EdgyModel | None, bool]] = []
        existing_records: dict[tuple, EdgyModel] = {}
        _unique_cols_and_update_fields: set = update_fields.union(unique_columns)
        can_result_cache = not self.embed_parent
        _update_columns: set[str] = {
            col
            for field in update_fields
            for col in queryset.model_class.meta.field_to_column_names[field]
        }
        concurrent_limit = 1 if getattr(queryset.database, "force_rollback", False) else None
        model_class = self.model_class
        proxy_model_class = cast("type[EdgyModel]", model_class.proxy_model)

        def _add_create_obj(
            obj: EdgyModel | dict,
            pos: int,
        ) -> tuple[EdgyModel | None, bool]:
            lookup_key = _extract_unique_lookup_key(
                obj, unique_fields or unique_columns, no_load=not unique_fields
            )
            if lookup_key and lookup_key in existing_records:
                return (None if none_on_existing else existing_records[lookup_key], False)
            created: EdgyModel
            if isinstance(obj, dict):
                created = model_class(
                    **{k: v for k, v in obj.items() if k in model_class.meta.fields}
                )
                create_params.append((created, pos, set(obj.keys())))
            else:
                created = obj
                create_params.append((created, pos, set(obj.meta.fields.keys())))
            if lookup_key:
                existing_records[lookup_key] = created
            return created, True

        if retrieve:
            # IMPROVEMENT TODO: move query part into a transaction and issue at best just one database query
            free_unique_columns: set[str] = {
                colname
                for colname in unique_columns
                if colname not in model_class.meta.columns_to_field
            }

            if unique_columns:

                async def _iterate_retrieve(
                    obj: EdgyModel | dict, pos: int
                ) -> tuple[EdgyModel | None, bool]:
                    if not isinstance(obj, (model_class, proxy_model_class, dict)):
                        raise ValueError(
                            f"Instance provided of wrong type: `{type(obj)!r}` required: `{model_class!r}`."
                        )
                    # try deduplicating before issuing a db query
                    lookup_key_precheck = (
                        None
                        if update
                        else _extract_unique_lookup_key(
                            obj, unique_fields or unique_columns, no_load=True
                        )
                    )
                    if lookup_key_precheck and lookup_key_precheck in existing_records:
                        return existing_records[lookup_key_precheck], False
                    filter_kwargs = {}
                    dict_fields = {}
                    incomplete = False
                    if isinstance(obj, dict):
                        for field in unique_fields:
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
                        for field in unique_fields:
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
                    lookup_key = _extract_unique_lookup_key(
                        obj, unique_fields or unique_columns, no_load=not unique_fields
                    )
                    if lookup_key and lookup_key in existing_records:
                        return existing_records[lookup_key], False
                    found_obj: EdgyModel | None = None
                    # prevent queries with user selected unique_fields/columns
                    if not incomplete:
                        # Using an array fixed an edgy-guardian bug when using databasez.iterate indirectly and
                        # is safe in case force_rollback is active
                        # Models can also issue loads by accessing attrs for building unique_fields
                        # For limiting use something like QuerySet.limit(100).bulk_get_or_create(...)
                        for instance in await queryset.update_embed_parent(None).filter(
                            **filter_kwargs
                        ):
                            if all(
                                # compare dicts
                                getattr(instance, k) == expected
                                for k, expected in dict_fields.items()
                            ):
                                lookup_key = _extract_unique_lookup_key(
                                    instance,
                                    unique_fields or unique_columns,
                                    no_load=not unique_fields,
                                )
                                assert lookup_key is not None, (
                                    "invalid fields/attributes in unique_fields"
                                )
                                if lookup_key:
                                    if lookup_key not in existing_records:
                                        found_obj = existing_records[lookup_key] = instance
                                    else:
                                        found_obj = existing_records[lookup_key]
                                else:
                                    found_obj = instance
                                break
                    if found_obj is not None:
                        if update:
                            if isinstance(obj, dict):
                                for key in update_fields:
                                    if key in obj:
                                        setattr(found_obj, key, obj[key])
                            else:
                                for key in update_fields:
                                    if hasattr(obj, key):
                                        setattr(found_obj, key, getattr(obj, key))
                            update_objs.append(found_obj)
                        return None if none_on_existing else found_obj, False
                    elif create:
                        return _add_create_obj(obj, pos)
                    else:
                        return None, False

                returned_objs_with_created_with_null = await run_concurrently(
                    [_iterate_retrieve(obj, pos) for pos, obj in enumerate(objs)],
                    limit=concurrent_limit,
                )
        elif create:
            for pos, obj in enumerate(objs):
                returned_objs_with_created_with_null.append(_add_create_obj(obj, pos))
        elif update:
            # update is last, if creation fails fallback to update
            for obj in objs:
                updated: EdgyModel
                if isinstance(obj, dict):
                    updated = proxy_model_class(**obj)
                else:
                    updated = obj
                    if not isinstance(updated, model_class | proxy_model_class):
                        raise ValueError(
                            f"Instance provided of wrong type: `{type(updated)!r}` required: `{model_class!r}`."
                        )
                if updated.can_load:
                    update_objs.append(updated)
                    returned_objs_with_created_with_null.append((updated, False))
                else:
                    returned_objs_with_created_with_null.append((None, False))

        if resolve_embed and self.embed_parent:
            # check if all are elligable and can be resolved
            if not all(
                res[0] is None or res[0].can_load or res[1]
                for res in returned_objs_with_created_with_null
            ):
                raise QuerySetError(
                    detail="Not all resulting objects are fully defined for loading and `resolve_embed=True`",
                )
            can_result_cache = True

        check_db_connection(queryset.database, 4)
        con_lock = asyncio.Lock()

        async def _iterate_create(
            item: tuple[EdgyModel, int, set[str]],
            connection: Connection,
            returning: list[sqlalchemy.ColumnElement],
        ) -> dict[str, Any] | None:
            original_field_values = item[0].extract_db_fields()
            col_values: dict[str, Any] = item[0].extract_column_values(
                original_field_values,
                phase="prepare_insert",
                instance=used_instance,
                model_instance=item[0],
            )
            if model_class.meta.pre_save_fields:
                col_values.update(
                    await item[0].execute_pre_save_hooks(
                        col_values, original_field_values, is_update=False
                    )
                )
            if ignore_create_conflicts or (
                resolve_embed and self.embed_parent and not item[0].can_load
            ):
                try:
                    # con_lock ensures only one userlandthread is accessing the database concurrently
                    # so the transaction is correctly mapped
                    async with con_lock, connection.transaction():
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
                        for col_name, col_key in model_class.meta.columns_remapping.items():
                            if col_name in returned_mapping:
                                returned_mapping[col_key] = returned_mapping.pop(col_name)
                        col_values.update(returned_mapping)

                        new_kwargs = model_class.transform_input(
                            col_values, phase="post_insert", instance=self, model_instance=item[0]
                        )
                        item[0].__dict__.update(new_kwargs)
                except IntegrityError:
                    if not ignore_create_conflicts:
                        raise
                    if update and item[0].can_load:
                        # we can do an update, but not a retrieval because
                        # a retrieval doesn't overwrite the potential wrong values
                        # maybe still issue a load afterwards
                        # we need to be **sure** that the instance is loadable and copy the `identifying_db_fields`
                        # othewise we can end with an invalid proxy
                        proxy = proxy_model_class(
                            **item[0].extract_db_fields(_unique_cols_and_update_fields)
                        )
                        proxy.identifying_db_fields = item[0].identifying_db_fields
                        update_objs.append(proxy)
                        returned_objs_with_created_with_null[item[1]] = (proxy, False)
                        skip_post_save.add(id(item[0]))
                    else:
                        # always return None because we don't know why it failed or we can't recover
                        returned_objs_with_created_with_null[item[1]] = (None, False)
                        skip_post_save.add(id(item[0]))
                return None
            return col_values

        async def _iterate_update(obj: EdgyModel) -> dict[str, Any]:
            original_field_values = obj.extract_db_fields(_unique_cols_and_update_fields)
            # copied from update
            col_values: dict[str, Any] = model_class.extract_column_values(
                original_field_values,
                is_update=True,
                is_partial=True,
                phase="prepare_update",
                instance=used_instance,
                model_instance=obj,
            )
            if model_class.meta.pre_save_fields:
                col_values.update(
                    await obj.execute_pre_save_hooks(
                        col_values, original_field_values, is_update=True
                    )
                )
            if not _update_columns.issubset(col_values):
                raise QuerySetError(
                    detail=f"Missing columns: {_update_columns.difference(col_values)}. Check `update_fields` or the input values."
                )
            new_kwargs = model_class.transform_input(
                col_values, phase="post_update", instance=self, model_instance=obj
            )
            obj.__dict__.update(new_kwargs)
            return {f"__{item[0]}": item[1] for item in col_values.items()}

        token = CURRENT_INSTANCE.set(used_instance)
        try:
            async with (
                queryset.database as database,
                database.transaction(),
                database.connection() as connection,
            ):
                create_obj_values: list[dict | None] = []
                if create_params:
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
                                    _iterate_create(tup, connection, returning)
                                    for tup in create_params
                                ],
                                limit=concurrent_limit,
                            )
                        )
                        if val is not None
                    ]
                    # we need to recheck if the conditions are still valid
                    if create_obj_values:
                        expression_create = queryset.table.insert().values(create_obj_values)
                        await connection.execute_many(expression_create)
                # prevent calling db with empty iterable, this causes errors
                if update_objs:
                    update_obj_values = await run_concurrently(
                        [_iterate_update(obj) for obj in update_objs],
                        limit=concurrent_limit,
                    )
                    # by default pknames
                    unique_query_placeholder = (
                        getattr(queryset.table.c, col)
                        == sqlalchemy.bindparam(
                            f"__{col}",
                            type_=getattr(queryset.table.c, col).type,
                        )
                        for col in unique_columns
                    )
                    expression_update = queryset.table.update().where(*unique_query_placeholder)
                    values_placeholder: dict[str, Any] = {
                        col: sqlalchemy.bindparam(
                            f"__{col}", type_=getattr(queryset.table.c, col).type
                        )
                        for col in _update_columns
                    }
                    expression_update = expression_update.values(values_placeholder)
                    await connection.execute_many(expression_update, update_obj_values)

                if update_objs or create_params:
                    # only the results change
                    self._clear_cache(
                        keep_cached_selected=True,
                        keep_result_cache=can_result_cache,
                    )
                    operations: list[Awaitable] = []
                    if model_class.meta.post_save_fields:
                        operations.extend(
                            tup[0].execute_post_save_hooks(tup[2], is_update=False)
                            # otherwise we would execute twice or one time for non-existing rows
                            for tup in create_params
                            if id(tup[0]) not in skip_post_save
                        )
                        if not model_class.meta.post_save_fields.isdisjoint(update_fields):
                            operations.extend(
                                obj.execute_post_save_hooks(update_fields, is_update=True)
                                for obj in update_objs
                                # we currently doesn't put update_objs in skip_post_save
                            )
                    if operations:
                        await run_concurrently(
                            operations,
                            limit=concurrent_limit,
                        )
        finally:
            CURRENT_INSTANCE.reset(token)
        if not self.embed_parent:
            self._cache.update(
                model_class,
                [
                    tup[0]
                    for tup in returned_objs_with_created_with_null
                    if tup[0] is not None and tup[0].can_load
                ],
                cache_keys=[
                    self._cache.create_cache_key(model_class, tup[0])
                    for tup in returned_objs_with_created_with_null
                    if tup[0] is not None and tup[0].can_load
                ],
            )
        elif resolve_embed:
            immediate = await run_concurrently(
                [
                    self._embed_parent_in_result(tup[0])
                    for tup in returned_objs_with_created_with_null
                ],
                limit=concurrent_limit,
            )
            self._cache.update(
                self.model_class,
                [item[1] for item in immediate if item[0] is not None],
                cache_keys=[
                    self._cache.create_cache_key(model_class, item[0])
                    for item in immediate
                    if item[0] is not None
                ],
            )

            return cast(
                "list[tuple[EdgyEmbedTarget | None, bool]]",
                list(
                    zip(
                        [item[1] for item in immediate],
                        (res[1] for res in returned_objs_with_created_with_null),
                        strict=True,
                    )
                ),
            )
        return returned_objs_with_created_with_null

    async def bulk_create(
        self,
        objs: Iterable[dict[str, Any] | EdgyModel],
        *,
        ignore_conflicts: bool = False,
        resolve_embed: bool = False,
    ) -> list[EdgyModel | None] | list[EdgyEmbedTarget | None]:
        """
        Bulk creates multiple records in a single batch operation.

        This method bypasses model-level save hooks (except for pre/post-save) for efficiency,
        and returns plain instances which **may** are incomplete.

        Args:
            objs (Iterable[dict[str, Any] | EdgyModel]): An iterable of dictionaries or
                                                         model instances to create.
        Kwargs:
            ignore_conflicts (bool): Ignore insert conflicts. Support varies between database systems.
            resolve_embed (bool): Triggers mode in which embedding is applied when True.

        Returns:
            list[EdgyModel] | list[EdgyEmbedTarget]:
                A list of created objects.
                Warning: for performance reasons no embedding is applied by default and
                the returned objects are maybe incomplete (check `can_load` property).
        """
        return cast(
            "list[EdgyModel | None] | list[EdgyEmbedTarget | None]",
            [
                tup[0]
                for tup in await self._bulk_get_update_or_create(
                    objs=objs,
                    unique_columns=self.model_class.pkcolumns,
                    create=True,
                    update=False,
                    retrieve=False,
                    resolve_embed=resolve_embed,
                    none_on_existing=ignore_conflicts,
                    ignore_create_conflicts=ignore_conflicts,
                )
            ],
        )

    bulk_insert = bulk_create

    async def bulk_update(
        self,
        objs: Iterable[dict[str, Any] | EdgyModel],
        *,
        update_fields: Iterable[str] | None = None,
        unique_fields: Iterable[str] | None = None,
        fields: Iterable[str] | None = None,
        resolve_embed: bool = False,
    ) -> list[EdgyModel | None] | list[EdgyEmbedTarget | None]:
        """
        Update multiple objects in a single bulk operation.

        Args:
            objs (Iterable[dict[str, Any] | EdgyModel]): A sequence of model instances to update.
        Kwargs:
            update_fields (Iterable[str]): A list of field names to update for each object. If None use all fields.
            unique_fields (Iterable[str] | None): Fields that determine uniqueness.
                                                    If None, pknames are used. If empty it fails.
            resolve_embed (bool): Triggers mode in which embedding is applied when True.

        Returns:
            list[EdgyModel] | list[EdgyEmbedTarget]:
                A list of updated objects.
                Warning: for performance reasons no embedding is applied by default and
                the returned objects are maybe incomplete (check `can_load` property).
        """
        if fields is not None:
            warnings.warn(
                "Use `update_fields` instead `fields`.", DeprecationWarning, stacklevel=2
            )
            update_fields = fields
        _unique_fields: set[str] = set()
        _unique_columns: Sequence[str]
        if unique_fields is None:
            _unique_columns = self.model_class.pkcolumns
        else:
            _unique_fields = set(unique_fields)
            if not _unique_fields:
                raise ValueError("`unique_fields` empty.")
            _unique_columns = tuple(
                col
                for field in _unique_fields
                for col in self.model_class.meta.field_to_column_names[field]
            )

        _update_fields = (
            {
                key
                for key, value in self.model_class.meta.fields.items()
                if not value.read_only and not value.primary_key
            }
            if update_fields is None
            else set(update_fields)
        )
        return cast(
            "list[EdgyModel | None] | list[EdgyEmbedTarget | None]",
            [
                tup[0]
                for tup in await self._bulk_get_update_or_create(
                    objs=objs,
                    # Somehow this is required to be non-empty
                    unique_fields=_unique_fields or _unique_columns,
                    unique_columns=_unique_columns,
                    update_fields=_update_fields,
                    update=True,
                    retrieve=resolve_embed,
                    create=False,
                    resolve_embed=resolve_embed,
                )
            ],
        )

    async def bulk_update_or_create(
        self,
        objs: Iterable[dict[str, Any] | EdgyModel],
        *,
        update_fields: Iterable[str] | None = None,
        unique_fields: Iterable[str] | None = None,
        resolve_embed: bool = False,
    ) -> list[tuple[EdgyModel | None, bool]] | list[tuple[EdgyEmbedTarget | None, bool]]:
        """
        Bulk updates or creates records in a table.

        If records exist based on unique fields, they are retrieved.
        Otherwise, new records are created.

        Args:
            objs (Sequence[Union[dict[str, Any], EdgyModel]]): A list of objects or dictionaries.
        Kwargs:
            update_fields (Iterable[str]): A list of field names to update for each object (when found).
                                    If None use all fields.
            unique_fields (Iterable[str] | None): Fields that determine uniqueness.
                                                  If None, pknames are used. If empty it fails.
            resolve_embed (bool): Triggers mode in which embedding is applied when True.

        Returns:
            list[tuple[EdgyModel, bool]] | list[tuple[EdgyEmbedTarget, bool]]:
                A list of `(instance, created)` tuples.
                Warning: for performance reasons no embedding is applied by default and
                the returned objects are maybe incomplete (check `can_load` property).
                Warning: you might want to issue a load to get correct data outside of update_fields.
        """
        _unique_fields: set[str] = set()
        _unique_columns: set[str]
        if unique_fields is None:
            _unique_columns = set(self.model_class.pkcolumns)
        else:
            _unique_fields = set(unique_fields)
            if not _unique_fields:
                raise ValueError("`unique_fields` empty.")
            _unique_columns = {
                col
                for field in _unique_fields
                for col in self.model_class.meta.field_to_column_names[field]
            }
        _update_fields = (
            {
                key
                for key, value in self.model_class.meta.fields.items()
                if not value.read_only and not value.primary_key
            }
            if update_fields is None
            else set(update_fields)
        )
        unique_equals_pk = set(self.model_class.pkcolumns) == _unique_columns
        return cast(
            "list[tuple[EdgyModel | None, bool]] | list[tuple[EdgyEmbedTarget  | None, bool]]",
            await self._bulk_get_update_or_create(
                objs=objs,
                unique_fields=_unique_fields,
                unique_columns=_unique_columns,
                update_fields=_update_fields,
                create=True,
                update=True,
                # if unique_equals_pk we can just issue an insert and check if there was a conflict
                # this allows us to sidestep the retrieve mechanic
                # for resolve_embed the other mechanic is implicitly used
                retrieve=not unique_equals_pk,
                ignore_create_conflicts=unique_equals_pk,
                resolve_embed=resolve_embed,
            ),
        )

    async def bulk_get_or_create(
        self,
        objs: Iterable[dict[str, Any] | EdgyModel],
        *,
        unique_fields: Iterable[str] | None = None,
        resolve_embed: bool = False,
    ) -> list[tuple[EdgyModel, bool]] | list[tuple[EdgyEmbedTarget, bool]]:
        """
        Bulk gets or creates records in a table.

        If records exist based on unique fields, they are retrieved.
        Otherwise, new records are created.

        Args:
            objs (Iterable[Union[dict[str, Any], EdgyModel]]): A list of objects or dictionaries.
        Kwargs:
            unique_fields (Iterable[str] | None): Fields that determine uniqueness.
                                                  If None, pknames are used. If empty it fails.
            resolve_embed (bool): Triggers mode in which embedding is applied when True.

        Returns:
            list[tuple[EdgyModel, bool]] | list[tuple[EdgyEmbedTarget, bool]]:
                A list of tuples with retrieved or newly created objects and created flag.
                Warning: for performance reasons no embedding is applied by default and
                the returned objects are maybe incomplete (check `can_load` property).
        """

        _unique_fields: set[str] = set()
        _unique_columns: Collection[str]
        if unique_fields is None:
            _unique_fields = set(self.model_class.pknames)
            _unique_columns = self.model_class.pkcolumns
        else:
            _unique_fields = set(unique_fields)
            if not _unique_fields:
                raise ValueError("`unique_fields` empty.")
            _unique_columns = {
                col
                for field in _unique_fields
                for col in self.model_class.meta.field_to_column_names[field]
            }
        return cast(
            "list[tuple[EdgyModel, bool]] | list[tuple[EdgyEmbedTarget, bool]]",
            await self._bulk_get_update_or_create(
                objs=objs,
                unique_fields=_unique_fields,
                unique_columns=_unique_columns,
                create=True,
                update=False,
                retrieve=True,
                resolve_embed=resolve_embed,
            ),
        )

    bulk_select_or_insert = bulk_get_or_create
