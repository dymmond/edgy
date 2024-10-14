import asyncio
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Optional

from edgy.core.db.fields.base import RelationshipField
from edgy.core.db.models.utils import apply_instance_extras
from edgy.core.db.querysets.prefetch import Prefetch, check_prefetch_collision
from edgy.core.db.relationships.utils import crawl_relationship
from edgy.exceptions import QuerySetError

if TYPE_CHECKING:  # pragma: no cover
    from sqlalchemy import Table
    from sqlalchemy.engine.result import Row

    from edgy import Database, Model
    from edgy.core.db.models.types import BaseModelType


class ModelRowMixin:
    """
    Builds a row for a specific model
    """

    @classmethod
    def can_load_from_row(cls: type["Model"], row: "Row", table: "Table") -> bool:
        """Check if a model_class can be loaded from a row for the table."""

        return bool(
            cls.meta.registry is not None
            and not cls.meta.abstract
            and all(
                row._mapping.get(f"{table.key.replace('.', '_')}_{col}") is not None
                for col in cls.pkcolumns
            )
        )

    @classmethod
    async def from_sqla_row(
        cls: type["Model"],
        row: "Row",
        # contain the mappings used for select
        tables_and_models: dict[str, tuple["Table", type["BaseModelType"]]],
        select_related: Optional[Sequence[Any]] = None,
        prefetch_related: Optional[Sequence["Prefetch"]] = None,
        only_fields: Sequence[str] = None,
        is_defer_fields: bool = False,
        exclude_secrets: bool = False,
        using_schema: Optional[str] = None,
        database: Optional["Database"] = None,
        prefix: str = "",
        old_select_related_value: Optional["Model"] = None,
    ) -> Optional["Model"]:
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

            # stop selecting when None. Related models are not available.
            if not model_class.can_load_from_row(
                row,
                tables_and_models[
                    model_class.meta.tablename
                    if using_schema is None
                    else f"{using_schema}.{model_class.meta.tablename}"
                ][0],
            ):
                continue
            _prefix = field_name if not prefix else f"{prefix}__{field_name}"

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
                )
        # don't overwrite, update with new values and return
        if old_select_related_value:
            for k, v in item.items():
                setattr(old_select_related_value, k, v)
            return old_select_related_value
        table_columns = tables_and_models[
            cls.meta.tablename if using_schema is None else f"{using_schema}.{cls.meta.tablename}"
        ][0].columns
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
                if (
                    column is not None
                    and f"{column.table.key.replace('.', '_')}_{column.key}" in row._mapping
                ):
                    child_item[foreign_key.from_fk_field_name(related, column_name)] = (
                        row._mapping[f"{column.table.key.replace('.', '_')}_{column.key}"]
                    )
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

            item[related] = proxy_model

        # Check for the only_fields
        # Pull out the regular column values.
        for column in table_columns:
            if (
                only_fields
                and prefix not in only_fields
                and (f"{prefix}__{column.key}" if prefix else column.key) not in only_fields
            ):
                continue
            if column.key in secret_columns:
                continue
            if column.key not in cls.meta.columns_to_field:
                continue
            # set if not of an foreign key with one column
            elif (
                column.key not in item
                and f"{column.table.key.replace('.', '_')}_{column.key}" in row._mapping
            ):
                item[column.key] = row._mapping[
                    f"{column.table.key.replace('.', '_')}_{column.key}"
                ]
        model: Model = (
            cls.proxy_model(**item, __phase__="init_db")  # type: ignore
            if exclude_secrets or is_defer_fields or only_fields
            else cls(**item, __phase__="init_db")
        )
        # Apply the schema to the model
        model = apply_instance_extras(
            model,
            cls,
            using_schema,
            database=database,
            table=tables_and_models[
                cls.meta.tablename
                if using_schema is None
                else f"{using_schema}.{cls.meta.tablename}"
            ][0],
        )

        # Handle prefetch related fields.
        await cls.__handle_prefetch_related(
            row=row,
            table=tables_and_models[
                cls.meta.tablename
                if using_schema is None
                else f"{using_schema}.{cls.meta.tablename}"
            ][0],
            model=model,
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
    def create_model_key_from_sqla_row(
        cls,
        row: "Row",
    ) -> tuple:
        """
        Build a cache key for the model.
        """
        pk_key_list: list[Any] = [cls.__name__]
        for attr in cls.pkcolumns:
            try:
                pk_key_list.append(str(row._mapping[getattr(cls.table.columns, attr)]))
            except KeyError:
                pk_key_list.append(str(row._mapping[attr]))
        return tuple(pk_key_list)

    @classmethod
    async def __set_prefetch(
        cls,
        row: "Row",
        table: "Table",
        model: "Model",
        related: "Prefetch",
    ) -> None:
        model_key = ()
        if related._is_finished:
            await related.init_bake(type(model))
            model_key = model.create_model_key()
        if model_key in related._baked_results:
            setattr(model, related.to_attr, related._baked_results[model_key])
        else:
            clauses = []
            for pkcol in cls.pkcolumns:
                clauses.append(
                    getattr(table.columns, pkcol)
                    == row._mapping[f"{table.key.replace('.', '_')}_{pkcol}"]
                )
            queryset = related.queryset
            if related._is_finished:
                assert queryset is not None, "Queryset is not set but _is_finished flag"
            else:
                check_prefetch_collision(model, related)
                crawl_result = crawl_relationship(
                    model.__class__, related.related_name, traverse_last=True
                )
                if queryset is None:
                    if crawl_result.reverse_path is False:
                        queryset = model.__class__.query.all()
                    else:
                        queryset = crawl_result.model_class.query.all()

                if queryset.model_class == model.__class__:
                    # queryset is of this model
                    queryset = queryset.select_related(related.related_name)
                    queryset.embed_parent = (related.related_name, "")
                elif crawl_result.reverse_path is False:
                    QuerySetError(
                        detail=(
                            f"Creating a reverse path is not possible, unidirectional fields used."
                            f"You may want to use as queryset a queryset of model class {model!r}."
                        )
                    )
                else:
                    # queryset is of the target model
                    queryset = queryset.select_related(crawl_result.reverse_path)
            setattr(model, related.to_attr, await queryset.filter(*clauses))

    @classmethod
    async def __handle_prefetch_related(
        cls,
        row: "Row",
        table: "Table",
        model: "Model",
        prefetch_related: Sequence["Prefetch"],
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
            queries.append(cls.__set_prefetch(row=row, table=table, model=model, related=related))
        if queries:
            await asyncio.gather(*queries)
