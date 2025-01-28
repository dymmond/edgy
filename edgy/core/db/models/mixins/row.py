from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Optional, cast

from edgy.core.db.fields.base import RelationshipField
from edgy.core.db.models.utils import apply_instance_extras
from edgy.core.db.querysets.prefetch import Prefetch, check_prefetch_collision
from edgy.core.db.relationships.utils import crawl_relationship
from edgy.exceptions import QuerySetError

if TYPE_CHECKING:  # pragma: no cover
    from sqlalchemy import Table
    from sqlalchemy.engine.result import Row

    from edgy.core.connection import Database
    from edgy.core.db.models.model import Model
    from edgy.core.db.models.types import BaseModelType
    from edgy.core.db.querysets.types import reference_select_type


class ModelRowMixin:
    """
    Builds a row for a specific model
    """

    @classmethod
    def can_load_from_row(cls: type[Model], row: Row, table: Table) -> bool:
        """Check if a model_class can be loaded from a row for the table."""

        return bool(
            cls.meta.registry
            and not cls.meta.abstract
            and all(row._mapping.get(f"{table.name}_{col}") is not None for col in cls.pkcolumns)
        )

    @classmethod
    async def from_sqla_row(
        cls: type[Model],
        row: Row,
        # contain the mappings used for select
        tables_and_models: dict[str, tuple[Table, type[BaseModelType]]],
        select_related: Optional[Sequence[Any]] = None,
        prefetch_related: Optional[Sequence[Prefetch]] = None,
        only_fields: Sequence[str] = None,
        is_defer_fields: bool = False,
        exclude_secrets: bool = False,
        using_schema: Optional[str] = None,
        database: Optional[Database] = None,
        prefix: str = "",
        old_select_related_value: Optional[Model] = None,
        reference_select: Optional[reference_select_type] = None,
    ) -> Optional[Model]:
        """
        Class method to convert a SQLAlchemy Row result into a EdgyModel row type.

        Looping through select_related fields if the query comes from a select_related operation.
        Validates if exists the select_related and related_field inside the models.

        When select_related and related_field exist for the same field being validated, the related
        field is ignored as it won't override the value already collected from the select_related.

        If there is no select_related, then goes through the related field where it **should**
        only return the instance of the the ForeignKey with the ID, making it lazy loaded.

        :return: Model class.
        """
        _reference_select: reference_select_type = (
            reference_select if reference_select is not None else {}
        )
        item: dict[str, Any] = {}
        select_related = select_related or []
        prefetch_related = prefetch_related or []
        secret_columns: set[str] = set()
        if exclude_secrets:
            for name in cls.meta.secret_fields:
                secret_columns.update(cls.meta.field_to_column_names[name])

        for related in select_related:
            field_name = related.split("__", 1)[0]
            try:
                field = cls.meta.fields[field_name]
            except KeyError:
                raise QuerySetError(
                    detail=f'Selected field "{field_name}cast("Model", " does not exist on {cls}.'
                ) from None
            if isinstance(field, RelationshipField):
                model_class, _, remainder = field.traverse_field(related)
            else:
                raise QuerySetError(
                    detail=f'Selected field "{field_name}" is not a RelationshipField on {cls}.'
                ) from None

            _prefix = field_name if not prefix else f"{prefix}__{field_name}"
            # stop selecting when None. Related models are not available.
            if not model_class.can_load_from_row(
                row,
                tables_and_models[_prefix][0],
            ):
                continue
            reference_select_sub = _reference_select.get(field_name)
            if not isinstance(reference_select_sub, dict):
                reference_select_sub = {}

            if remainder:
                # don't pass table, it is only for the main model_class
                item[field_name] = await model_class.from_sqla_row(
                    row,
                    tables_and_models=tables_and_models,
                    select_related=[remainder],
                    prefetch_related=prefetch_related,
                    exclude_secrets=exclude_secrets,
                    is_defer_fields=is_defer_fields,
                    using_schema=using_schema,
                    database=database,
                    prefix=_prefix,
                    old_select_related_value=item.get(field_name),
                    reference_select=reference_select_sub,
                )
            else:
                # don't pass table, it is only for the main model_class
                item[field_name] = await model_class.from_sqla_row(
                    row,
                    tables_and_models=tables_and_models,
                    exclude_secrets=exclude_secrets,
                    is_defer_fields=is_defer_fields,
                    using_schema=using_schema,
                    database=database,
                    prefix=_prefix,
                    old_select_related_value=item.get(field_name),
                    reference_select=reference_select_sub,
                )
        # don't overwrite, update with new values and return
        if old_select_related_value:
            for k, v in item.items():
                setattr(old_select_related_value, k, v)
            return old_select_related_value
        table_columns = tables_and_models[prefix][0].columns
        # Populate the related names
        # Making sure if the model being queried is not inside a select related
        # This way it is not overritten by any value
        for related in cls.meta.foreign_key_fields:
            foreign_key = cls.meta.fields[related]
            ignore_related: bool = cls.__should_ignore_related_name(related, select_related)
            if ignore_related or related in cls.meta.secret_fields:
                continue
            if related in item:
                continue

            if exclude_secrets and foreign_key.secret:
                continue
            columns_to_check = foreign_key.get_column_names(related)

            model_related = foreign_key.target

            child_item = {}
            for column_name in columns_to_check:
                column = getattr(table_columns, column_name, None)
                if column_name is None:
                    continue
                columnkeyhash = column_name
                if prefix:
                    columnkeyhash = f"{tables_and_models[prefix][0].name}_{column.key}"

                if columnkeyhash in row._mapping:
                    child_item[foreign_key.from_fk_field_name(related, column_name)] = (
                        row._mapping[columnkeyhash]
                    )

            reference_select_child = _reference_select.get(related)
            extra_no_trigger_child: set[str] = set()
            if isinstance(reference_select_child, dict):
                for (
                    reference_target_child,
                    reference_source_child,
                ) in cast("reference_select_type", reference_select_child).items():
                    if isinstance(reference_source_child, dict) or not reference_source_child:
                        continue
                    extra_no_trigger_child.add(reference_target_child)
                    if isinstance(reference_source_child, str):
                        reference_source_child_parts = reference_source_child.rsplit("__", 1)
                        if (
                            len(reference_source_child_parts) == 2
                            and reference_source_child_parts[0] in tables_and_models
                        ):
                            reference_source_child = f"{tables_and_models[reference_source_child_parts[0]][0].name}_{reference_source_child_parts[1]}"
                    child_item[reference_target_child] = row._mapping[reference_source_child]

            # Make sure we generate a temporary reduced model
            # For the related fields. We simply chnage the structure of the model
            # and rebuild it with the new fields.
            proxy_model = model_related.proxy_model(**child_item)
            proxy_database = database if model_related.database is cls.database else None
            # don't pass a table. It is not in the row (select related path) and has not an explicit table
            proxy_model = apply_instance_extras(
                proxy_model,
                model_related,
                using_schema,
                database=proxy_database,
            )
            proxy_model.identifying_db_fields = foreign_key.related_columns
            proxy_model.__no_load_trigger_attrs__.update(extra_no_trigger_child)
            if exclude_secrets:
                proxy_model.__no_load_trigger_attrs__.update(model_related.meta.secret_fields)

            item[related] = proxy_model

        # Check for the only_fields
        # Pull out the regular column values.
        class_columns = cls.table.columns
        for column in table_columns:
            if (
                only_fields
                and prefix not in only_fields
                and (f"{prefix}__{column.key}" if prefix else column.key) not in only_fields
            ):
                continue
            if column.key in secret_columns:
                continue
            if column.key not in class_columns:
                # for supporting reflected we cannot use columns_to_field
                continue
            # set if not of an foreign key with one column
            if column.key in item:
                continue
            columnkeyhash = column.key
            if prefix:
                columnkeyhash = f"{tables_and_models[prefix][0].name}_{columnkeyhash}"

            if columnkeyhash in row._mapping:
                item[column.key] = row._mapping[columnkeyhash]
        for reference_target_main, reference_source_main in _reference_select.items():
            if isinstance(reference_source_main, dict) or not reference_source_main:
                continue

            if isinstance(reference_source_main, str):
                reference_source_main_parts = reference_source_main.rsplit("__", 1)
                if (
                    len(reference_source_main_parts) == 2
                    and reference_source_main_parts[0] in tables_and_models
                ):
                    reference_source_main = f"{tables_and_models[reference_source_main_parts[0]][0].name}_{reference_source_main_parts[1]}"
            # overwrite
            item[reference_target_main] = row._mapping[reference_source_main]
        model: Model = (
            cls.proxy_model(**item, __phase__="init_db")  # type: ignore
            if exclude_secrets or is_defer_fields or only_fields
            else cls(**item, __phase__="init_db")
        )
        # mark a model as completely loaded when no deferred is active
        if not is_defer_fields and not only_fields:
            model._loaded_or_deleted = True
        # hard exclude secrets from triggering load
        if exclude_secrets:
            model.__no_load_trigger_attrs__.update(cls.meta.secret_fields)
        # Apply the schema to the model
        model = apply_instance_extras(
            model,
            cls,
            using_schema,
            database=database,
            table=tables_and_models[prefix][0],
        )

        if prefetch_related:
            # Handle prefetch related fields.
            await cls.__handle_prefetch_related(
                row=row,
                prefix=prefix,
                model=model,
                tables_and_models=tables_and_models,
                prefetch_related=prefetch_related,
            )
        assert model.pk is not None, model
        return model

    @classmethod
    def __should_ignore_related_name(
        cls, related_name: str, select_related: Sequence[str]
    ) -> bool:
        """
        Validates if it should populate the related field if select related is not considered.
        """
        for related_field in select_related:
            fields = related_field.split("__")
            if related_name in fields:
                return True
        return False

    @classmethod
    def create_model_key_from_sqla_row(cls, row: Row, row_prefix: str = "") -> tuple:
        """
        Build a cache key for the model.
        """
        pk_key_list: list[Any] = [cls.__name__]
        for attr in cls.pkcolumns:
            pk_key_list.append(str(row._mapping[f"{row_prefix}{attr}"]))
        return tuple(pk_key_list)

    @classmethod
    async def __set_prefetch(
        cls,
        row: Row,
        model: Model,
        row_prefix: str,
        related: Prefetch,
    ) -> None:
        model_key = ()
        if related._is_finished:
            # when force_rollback
            # we can only bake after all rows are retrieved
            # this is why it is here
            await related.init_bake(type(model))
            model_key = model.create_model_key()
        if model_key in related._baked_results:
            setattr(model, related.to_attr, related._baked_results[model_key])
        else:
            crawl_result = crawl_relationship(
                model.__class__, related.related_name, traverse_last=True
            )
            if crawl_result.reverse_path is False:
                QuerySetError(
                    detail=("Creating a reverse path is not possible, unidirectional fields used.")
                )
            if crawl_result.cross_db_remainder:
                raise NotImplementedError(
                    "Cannot prefetch from other db yet. Maybe in future this feature will be added."
                )
            queryset = related.queryset
            if related._is_finished:
                assert queryset is not None, "Queryset is not set but _is_finished flag"
            else:
                check_prefetch_collision(model, related)
                if queryset is None:
                    queryset = crawl_result.model_class.query.all()

                queryset = queryset.select_related(cast(str, crawl_result.reverse_path))
            clause = {
                f"{crawl_result.reverse_path}__{pkcol}": row._mapping[f"{row_prefix}{pkcol}"]
                for pkcol in cls.pkcolumns
            }
            setattr(model, related.to_attr, await queryset.filter(clause))

    @classmethod
    async def __handle_prefetch_related(
        cls,
        row: Row,
        model: Model,
        prefix: str,
        tables_and_models: dict[str, tuple[Table, type[BaseModelType]]],
        prefetch_related: Sequence[Prefetch],
    ) -> None:
        """
        Handles any prefetch related scenario from the model.
        Loads in advance all the models needed for a specific record

        Recursively checks for the related field and validates if there is any conflicting
        attribute. If there is, a `QuerySetError` is raised.
        """

        queries = []

        for related in prefetch_related:
            # Check for conflicting names
            # Check as early as possible
            check_prefetch_collision(model=model, related=related)
            row_prefix = f"{tables_and_models[prefix].name}_" if prefix else ""
            queries.append(
                cls.__set_prefetch(row=row, row_prefix=row_prefix, model=model, related=related)
            )
        if queries:
            await asyncio.gather(*queries)
