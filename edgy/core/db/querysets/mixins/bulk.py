from __future__ import annotations

import warnings
from collections.abc import (
    Awaitable,
    Iterable,
    Sequence,
)
from typing import (
    TYPE_CHECKING,
    Any,
    Literal,
    cast,
    overload,
)

import orjson
import sqlalchemy

from edgy.core.db.context_vars import CURRENT_INSTANCE
from edgy.core.utils.concurrency import run_concurrently
from edgy.core.utils.db import check_db_connection
from edgy.exceptions import BulkOperationModelsIncompatible

from ..types import (
    EdgyEmbedTarget,
    EdgyModel,
)

if TYPE_CHECKING:  # pragma: no cover
    from edgy.core.db.models.types import BaseModelType
    from edgy.core.db.querysets.queryset import QuerySet

_empty_set = cast(set[Any], frozenset())


def _extract_unique_lookup_key(obj: Any, unique_fields: Iterable[str]) -> tuple | None:
    """
    Extracts a unique lookup key from an object or dictionary.
    (Helper function, stays in base)
    """
    lookup_key = []
    if isinstance(obj, dict):
        for field in unique_fields:
            if field not in obj:
                return None
            value = obj[field]
            lookup_key.append(
                orjson.dumps(value, option=orjson.OPT_SORT_KEYS)
                if isinstance(value, dict | list)
                else value
            )
    else:
        for field in unique_fields:
            if not hasattr(obj, field):
                return None
            value = getattr(obj, field)
            lookup_key.append(
                orjson.dumps(value, option=orjson.OPT_SORT_KEYS)
                if isinstance(value, dict | list)
                else value
            )
    return tuple(lookup_key)


class BulkMixin:
    async def _bulk_get_update_or_create(
        self: QuerySet,
        *,
        objs: Iterable[dict[str, Any] | EdgyModel],
        resolve_embed: bool,
        unique_fields: set[str] = _empty_set,
        unique_columns: Sequence[str],
        update_fields: set[str] = _empty_set,
        update: bool,
        retrieve: bool,
    ) -> list[tuple[EdgyModel, bool]] | list[tuple[EdgyEmbedTarget, bool]]:
        """
        Bulk gets, updates or creates records in a table.

        If records exist based on unique fields, they are retrieved.
        Otherwise, new records are created.

        Args:
            objs (Iterable[Union[dict[str, Any], EdgyModel]]): A list of objects or dictionaries.
            unique_fields (set[str]): Fields that determine uniqueness.
            unique_columns (Sequence[str]): Columns that determine uniqueness.
            update_fields (set[str]): Fields which are updated.
            update (bool): Update retrieved objects.
            retrieve (bool): Retrieve objects. Otherwise update only path.

        Returns:
            tuple[list[EdgyModel], list[bool]]: A list of retrieved or newly created objects.
                                                Second list is True if it was an update.
        """
        queryset: QuerySet = self._clone()
        create_objs: list[EdgyModel] = []
        update_objs: list[EdgyModel] = []

        returned_objs_with_created: list[tuple[EdgyModel, bool]] = []
        create_skip_post_save: set[int] = set()
        existing_records: dict[tuple, EdgyModel] = {}
        model_class = self.model_class
        if retrieve:
            free_unique_columns: set[str] = {
                colname
                for colname in unique_columns
                if colname not in model_class.meta.columns_to_field
            }

            if unique_fields or free_unique_columns:

                async def _iterate_retrieve(obj: EdgyModel | dict) -> tuple[EdgyModel, bool]:
                    filter_kwargs = {}
                    dict_fields = {}
                    if isinstance(obj, dict):
                        for field in unique_fields:
                            if field in obj:
                                value = obj[field]
                                if isinstance(value, dict):
                                    dict_fields[field] = value
                                else:
                                    filter_kwargs[field] = value
                        for column in free_unique_columns:
                            if column in obj:
                                value = obj[column]
                                assert not isinstance(value, dict)
                                filter_kwargs[column] = value
                    else:
                        for field in unique_fields:
                            value = getattr(obj, field)
                            if isinstance(value, dict):
                                dict_fields[field] = value
                            else:
                                filter_kwargs[field] = value
                        for column in free_unique_columns:
                            if hasattr(obj, column):
                                value = getattr(obj, column)
                                assert not isinstance(value, dict)
                                filter_kwargs[column] = value
                    lookup_key = _extract_unique_lookup_key(obj, unique_fields)
                    if lookup_key is not None and lookup_key in existing_records:
                        return existing_records[lookup_key], False
                    found_obj: EdgyModel | None = None
                    # This fixes edgy-guardian bug when using databasez.iterate indirectly and
                    # is safe in case force_rollback is active
                    # Models can also issue loads by accessing attrs for building unique_fields
                    # For limiting use something like QuerySet.limit(100).bulk_get_or_create(...)
                    for instance in await queryset.update_embed_parent(None).filter(
                        **filter_kwargs
                    ):
                        if all(
                            getattr(instance, k) == expected for k, expected in dict_fields.items()
                        ):
                            lookup_key = _extract_unique_lookup_key(instance, unique_fields)
                            assert lookup_key is not None, (
                                "invalid fields/attributes in unique_fields"
                            )
                            if lookup_key not in existing_records:
                                found_obj = existing_records[lookup_key] = instance
                            else:
                                found_obj = existing_records[lookup_key]
                            break
                    if found_obj is None:
                        created = (
                            cast(EdgyModel, queryset.model_class(**obj))
                            if isinstance(obj, dict)
                            else obj
                        )
                        create_objs.append(created)
                        if (
                            model_class.meta.post_save_fields
                            and isinstance(obj, dict)
                            and model_class.meta.post_save_fields.isdisjoint(obj.keys())
                        ):
                            create_skip_post_save.add(id(created))
                        return created, True
                    else:
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
                        return found_obj, False

                returned_objs_with_created = await run_concurrently(
                    [_iterate_retrieve(obj) for obj in objs],
                    limit=(1 if getattr(queryset.database, "force_rollback", False) else None),
                )
        elif update:
            for obj in objs:
                updated = (
                    cast(EdgyModel, queryset.model_class(**obj)) if isinstance(obj, dict) else obj
                )
                update_objs.append(updated)
                returned_objs_with_created.append((updated, False))
        else:
            for obj in objs:
                created = (
                    cast(EdgyModel, queryset.model_class(**obj)) if isinstance(obj, dict) else obj
                )
                if (
                    model_class.meta.post_save_fields
                    and isinstance(obj, dict)
                    and model_class.meta.post_save_fields.isdisjoint(obj.keys())
                ):
                    create_skip_post_save.add(id(created))
                create_objs.append(created)
                returned_objs_with_created.append((created, True))

        _unique_and_update: set = update_fields.union(unique_fields)
        full_defined_for_cache: list[tuple[EdgyModel, EdgyModel]] = [
            (tup[0], tup[0]) for tup in returned_objs_with_created if tup[0].can_load
        ]
        if (
            resolve_embed
            and self.embed_parent
            and len(full_defined_for_cache) != len(returned_objs_with_created)
        ):
            raise BulkOperationModelsIncompatible(
                detail="Not all resulting objects are fully defined for loading and `resolve_embed=True`",
                instances_and_created=cast(
                    "list[tuple[BaseModelType, bool]]", returned_objs_with_created
                ),
            )

        check_db_connection(queryset.database, 4)

        async def _iterate_create(obj: EdgyModel) -> dict[str, Any]:
            original = obj.extract_db_fields()
            col_values: dict[str, Any] = obj.extract_column_values(
                original, phase="prepare_insert", instance=self, model_instance=obj
            )
            col_values.update(
                await obj.execute_pre_save_hooks(col_values, original, is_update=False)
            )
            return col_values

        async def _iterate_update(obj: EdgyModel) -> dict[str, Any]:
            extracted = obj.extract_db_fields(_unique_and_update)
            update_dict: dict[str, Any] = queryset.model_class.extract_column_values(
                extracted,
                is_update=True,
                is_partial=True,
                phase="prepare_update",
                instance=self,
                model_instance=obj,
            )
            if model_class.meta.pre_save_fields:
                update_dict.update(
                    await obj.execute_pre_save_hooks(update_dict, extracted, is_update=True)
                )
            return {f"__{item[0]}": item[1] for item in update_dict.items()}

        token = CURRENT_INSTANCE.set(self)
        try:
            async with queryset.database as database, database.transaction():
                # prevent calling db with empty iterable, this causes errors
                if update_objs:
                    update_obj_values = await run_concurrently(
                        [_iterate_update(obj) for obj in update_objs],
                        limit=(1 if getattr(queryset.database, "force_rollback", False) else None),
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
                        for field in update_fields
                        for col in queryset.model_class.meta.field_to_column_names[field]
                    }
                    expression_update = expression_update.values(values_placeholder)
                    await database.execute_many(expression_update, update_obj_values)

                if create_objs:
                    create_obj_values = await run_concurrently(
                        [_iterate_create(obj) for obj in create_objs],
                        limit=(1 if getattr(queryset.database, "force_rollback", False) else None),
                    )
                    expression_create = queryset.table.insert().values(create_obj_values)
                    await database.execute_many(expression_create)

                if update_objs or create_objs:
                    # only the results change
                    self._clear_cache(
                        keep_cached_selected=True,
                        keep_result_cache=len(full_defined_for_cache)
                        == len(returned_objs_with_created),
                    )
                    operations: list[Awaitable] = []
                    if model_class.meta.post_save_fields:
                        operations.extend(
                            obj.execute_post_save_hooks(
                                set(model_class.meta.fields.keys()), is_update=False
                            )
                            for obj in create_objs
                            if id(obj) not in create_skip_post_save
                        )
                        if not model_class.meta.post_save_fields.isdisjoint(update_fields):
                            operations.extend(
                                obj.execute_post_save_hooks(update_fields, is_update=True)
                                for obj in update_objs
                            )
                    if operations:
                        await run_concurrently(
                            operations,
                            limit=(
                                1 if getattr(queryset.database, "force_rollback", False) else None
                            ),
                        )
        finally:
            CURRENT_INSTANCE.reset(token)

        if not self.embed_parent:
            self._cache.update(
                model_class,
                full_defined_for_cache,
                cache_keys=[
                    self._cache.create_cache_key(model_class, tup[0])
                    for tup in full_defined_for_cache
                ],
            )
        elif resolve_embed:
            minstances, values = zip(
                *(
                    await run_concurrently(
                        [
                            self._embed_parent_in_result(res[0])
                            for res in returned_objs_with_created
                        ],
                        limit=(1 if getattr(queryset.database, "force_rollback", False) else None),
                    )
                ),
                strict=True,
            )
            self._cache.update(
                self.model_class,
                values,
                cache_keys=[self._cache.create_cache_key(model_class, key) for key in minstances],
            )

            return cast(
                "list[tuple[EdgyEmbedTarget, bool]]",
                list(zip(values, (res[1] for res in returned_objs_with_created), strict=True)),
            )
        return returned_objs_with_created

    @overload
    async def bulk_create(
        self, objs: Iterable[dict[str, Any] | EdgyModel], *, resolve_embed: Literal[True]
    ) -> list[EdgyEmbedTarget]:
        """
        Args:
            ...
            resolve_embed (True): Enables embedding.

        Returns:
            list[EdgyEmbedTarget]: A list of created objects.
                                   Warning: All models must be loadable (`can_load` property is true)
                                   otherwise an error is raised.
        """

    @overload
    async def bulk_create(
        self, objs: Iterable[dict[str, Any] | EdgyModel], *, resolve_embed: Literal[False] = False
    ) -> list[EdgyModel]:
        """
        Args:
            ...
            resolve_embed (False): Disables embedding. Default.
        Returns:
            list[EdgyModel]: A list of created objects.
                             Warning: for performance reasons no embedding is applied and
                             the returned objects are maybe incomplete (check `can_load` property).
        """

    async def bulk_create(
        self, objs: Iterable[dict[str, Any] | EdgyModel], resolve_embed: bool = False
    ) -> list[EdgyModel] | list[EdgyEmbedTarget]:
        """
        Bulk creates multiple records in a single batch operation.

        This method bypasses model-level save hooks (except for pre/post-save) for efficiency,
        and returns plain instances which **may** are incomplete.

        Args:
            objs (Iterable[dict[str, Any] | EdgyModel]): An iterable of dictionaries or
                                                         model instances to create.
            resolve_embed (bool): Triggers mode in which embedding is applied when True.

        Returns:
            list[EdgyModel] | list[EdgyEmbedTarget]:
                A list of created objects.
                Warning: for performance reasons no embedding is applied by default and
                the returned objects are maybe incomplete (check `can_load` property).
        """
        return cast(
            "list[EdgyModel] | list[EdgyEmbedTarget]",
            [
                tup[0]
                for tup in await self._bulk_get_update_or_create(
                    objs=objs,
                    unique_fields=set(self.model_class.pknames),
                    unique_columns=self.model_class.pkcolumns,
                    update=False,
                    retrieve=False,
                    resolve_embed=resolve_embed,
                )
            ],
        )

    bulk_insert = bulk_create

    @overload
    async def bulk_update(
        self,
        objs: Iterable[EdgyModel],
        *,
        update_fields: Iterable[str] | None = None,
        unique_fields: Iterable[str] | None = None,
        resolve_embed: Literal[True],
    ) -> list[EdgyEmbedTarget]:
        """
        Args:
            ...
            resolve_embed (True): Enables embedding.

        Returns:
            list[EdgyEmbedTarget]: A list of updated objects.
                                   Warning: All models must be loadable (`can_load` property is true)
                                   otherwise an error is raised.
        """

    @overload
    async def bulk_update(
        self,
        objs: Iterable[EdgyModel],
        *,
        update_fields: Iterable[str] | None = None,
        unique_fields: Iterable[str] | None = None,
        resolve_embed: Literal[False] = False,
    ) -> list[EdgyModel]:
        """
        Args:
            ...
            resolve_embed (False): Disables embedding. Default.
        Returns:
            list[EdgyModel]: A list of updated objects.
                             Warning: for performance reasons no embedding is applied and
                             the returned objects are maybe incomplete (check `can_load` property).
        """

    async def bulk_update(
        self,
        objs: Iterable[dict[str, Any] | EdgyModel],
        *,
        update_fields: Iterable[str] | None = None,
        unique_fields: Iterable[str] | None = None,
        fields: Iterable[str] | None = None,
        resolve_embed: bool = False,
    ) -> list[EdgyModel] | list[EdgyEmbedTarget]:
        """
        Update multiple objects in a single bulk operation.

        Args:
            objs (Iterable[EdgyModel]): A sequence of model instances to update.
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
        _unique_fields: set[str]
        _unique_columns: Sequence[str]
        if unique_fields is None:
            _unique_fields = set(self.model_class.pknames)
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
        return cast(
            "list[EdgyModel] | list[EdgyEmbedTarget]",
            [
                tup[0]
                for tup in await self._bulk_get_update_or_create(
                    objs=objs,
                    unique_fields=_unique_fields,
                    unique_columns=_unique_columns,
                    update_fields=set(
                        self.model_class.meta.fields.keys()
                        if update_fields is None
                        else update_fields
                    ),
                    update=True,
                    retrieve=False,
                    resolve_embed=resolve_embed,
                )
            ],
        )

    @overload
    async def bulk_update_or_create(
        self,
        objs: Iterable[dict[str, Any] | EdgyModel],
        *,
        update_fields: Iterable[str] | None = None,
        unique_fields: Iterable[str] | None = None,
        resolve_embed: Literal[True],
    ) -> list[tuple[EdgyEmbedTarget, bool]]:
        """
        Args:
            ...
            resolve_embed (True): Enables embedding.

        Returns:
            list[tuple[EdgyEmbedTarget, bool]]: A list of tuples with updated or created objects and created flag.
                                                Warning: All models must be loadable (`can_load` property is true)
                                                otherwise  `BulkOperationModelsIncompatible` is raised.
        """

    @overload
    async def bulk_update_or_create(
        self,
        objs: Iterable[dict[str, Any] | EdgyModel],
        *,
        update_fields: Iterable[str] | None = None,
        unique_fields: Iterable[str] | None = None,
        resolve_embed: Literal[False] = False,
    ) -> list[tuple[EdgyModel, bool]] | list[tuple[EdgyEmbedTarget, bool]]:
        """
        Args:
            resolve_embed (False): Disables embedding. Default.
        Returns:
            list[tuple[EdgyModel, bool]]: A list of tuples with updated or created objects and created flag.
                                          Warning: for performance reasons no embedding is applied and
                                          the returned objects are maybe incomplete (check `can_load` property).
        """

    async def bulk_update_or_create(
        self,
        objs: Iterable[dict[str, Any] | EdgyModel],
        *,
        update_fields: Iterable[str] | None = None,
        unique_fields: Iterable[str] | None = None,
        resolve_embed: bool = False,
    ) -> list[tuple[EdgyModel, bool]] | list[tuple[EdgyEmbedTarget, bool]]:
        """
        Bulk updates or creates records in a table.

        If records exist based on unique fields, they are retrieved.
        Otherwise, new records are created.

        Args:
            objs (Sequence[Union[dict[str, Any], EdgyModel]]): A list of objects or dictionaries.
            update_fields (Iterable[str]): A list of field names to update for each object (when found).
                                    If None use all fields.
            unique_fields (Iterable[str] | None): Fields that determine uniqueness.
                                                  If None, pknames are used. If empty it fails.
            resolve_embed (bool): Triggers mode in which embedding is applied when True.

        Returns:
            list[tuple[EdgyModel, bool]] | list[tuple[EdgyEmbedTarget, bool]]:
                A list of tuples with retrieved or created objects and created flag.
                Warning: for performance reasons no embedding is applied by default and
                the returned objects are maybe incomplete (check `can_load` property).
        """
        _unique_fields: set[str]
        _unique_columns: Sequence[str]
        if unique_fields is None:
            _unique_fields = set(self.model_class.pknames)
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
        return await self._bulk_get_update_or_create(
            objs=objs,
            unique_fields=_unique_fields,
            unique_columns=_unique_columns,
            update_fields=set(self.model_class.meta.fields.keys()).difference(
                self.model_class.pknames
            )
            if update_fields is None
            else set(update_fields),
            update=True,
            retrieve=True,
            resolve_embed=resolve_embed,
        )

    @overload
    async def bulk_get_or_create(
        self,
        objs: Iterable[dict[str, Any] | EdgyModel],
        *,
        unique_fields: Iterable[str] | None = None,
        resolve_embed: Literal[True],
    ) -> list[tuple[EdgyEmbedTarget, bool]]:
        """
        Args:
            ...
            resolve_embed (True): Enables embedding.

        Returns:
            list[tuple[EdgyEmbedTarget, bool]]: A list of tuples with retrieved or created objects and created flag.
                                                Warning: All models must be loadable (`can_load` property is true)
                                                otherwise `BulkOperationModelsIncompatible` is raised.
        """

    @overload
    async def bulk_get_or_create(
        self,
        objs: Iterable[dict[str, Any] | EdgyModel],
        *,
        unique_fields: Iterable[str] | None = None,
        resolve_embed: Literal[False] = False,
    ) -> list[tuple[EdgyModel, bool]]:
        """
        Args:
            ...
            resolve_embed (False): Disables embedding. Default.
        Returns:
            list[tuple[EdgyModel, bool]]: A list of tuples with retrieved or created objects and created flag.
                                          Warning: for performance reasons no embedding is applied and
                                          the returned objects are maybe incomplete (check `can_load` property).
        """

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
            unique_fields (Iterable[str] | None): Fields that determine uniqueness.
                                                  If None, pknames are used. If empty it fails.
            resolve_embed (bool): Triggers mode in which embedding is applied when True.

        Returns:
            list[tuple[EdgyModel, bool]] | list[tuple[EdgyEmbedTarget, bool]]:
                A list of tuples with retrieved or newly created objects and created flag.
                Warning: for performance reasons no embedding is applied by default and
                the returned objects are maybe incomplete (check `can_load` property).
        """

        _unique_fields: set[str]
        _unique_columns: Sequence[str]
        if unique_fields is None:
            _unique_fields = set(self.model_class.pknames)
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
        return await self._bulk_get_update_or_create(
            objs=objs,
            unique_fields=_unique_fields,
            unique_columns=_unique_columns,
            update=False,
            retrieve=True,
            resolve_embed=resolve_embed,
        )

    bulk_select_or_insert = bulk_get_or_create
