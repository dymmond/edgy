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


class ModelRowMixin:
    """
    Builds a row for a specific model
    """

    @classmethod
    async def from_sqla_row(
        cls: type["Model"],
        row: "Row",
        select_related: Optional[Sequence[Any]] = None,
        prefetch_related: Optional[Sequence["Prefetch"]] = None,
        is_only_fields: bool = False,
        only_fields: Sequence[str] = None,
        is_defer_fields: bool = False,
        exclude_secrets: bool = False,
        using_schema: Optional[str] = None,
        database: Optional["Database"] = None,
        # local only parameter
        table: Optional["Table"] = None,
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
            if remainder:
                # don't pass table, it is only for the main model_class
                item[field_name] = await model_class.from_sqla_row(
                    row,
                    select_related=[remainder],
                    prefetch_related=prefetch_related,
                    exclude_secrets=exclude_secrets,
                    using_schema=using_schema,
                    database=database,
                )
            else:
                # don't pass table, it is only for the main model_class
                item[field_name] = await model_class.from_sqla_row(
                    row,
                    exclude_secrets=exclude_secrets,
                    using_schema=using_schema,
                    database=database,
                )
        table_columns = cls.table_schema(using_schema).columns
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
                if column is not None and column in row._mapping:
                    child_item[foreign_key.from_fk_field_name(related, column_name)] = (
                        row._mapping[column]
                    )
            # Make sure we generate a temporary reduced model
            # For the related fields. We simply chnage the structure of the model
            # and rebuild it with the new fields.
            proxy_model = model_related.proxy_model(**child_item)
            # don't pass table, it is only for the main model_class
            proxy_database = database if model_related.database is cls.database else None
            proxy_model = apply_instance_extras(
                proxy_model, model_related, using_schema, database=proxy_database
            )
            proxy_model.identifying_db_fields = foreign_key.related_columns

            item[related] = proxy_model

        # Check for the only_fields
        _is_only = set()
        if is_only_fields:
            _is_only = {str(field) for field in (only_fields or row._mapping.keys())}
        # Pull out the regular column values.
        for column in table_columns:
            # Making sure when a table is reflected, maps the right fields of the ReflectModel
            if _is_only and column.key not in _is_only:
                continue
            if column.key in secret_columns:
                continue
            if column.key not in cls.meta.columns_to_field:
                continue
            # set if not of an foreign key with one column
            elif column.key not in item:
                if column in row._mapping:
                    item[column.key] = row._mapping[column]
                elif column.name in row._mapping:
                    # fallback, sometimes the column is not found
                    item[column.key] = row._mapping[column.name]
        model: Model = (
            cls(**item, __phase__="init_db")  # type: ignore
            if not exclude_secrets and not is_defer_fields and not _is_only
            else cls.proxy_model(**item)
        )
        # Apply the schema to the model
        model = apply_instance_extras(model, cls, using_schema, database=database, table=table)

        # Handle prefetch related fields.
        await cls.__handle_prefetch_related(
            row=row, model=model, prefetch_related=prefetch_related
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
    async def __set_prefetch(cls, row: "Row", model: "Model", related: "Prefetch") -> None:
        model_key = ()
        if related._is_finished:
            await related.init_bake(type(model))
            model_key = model.create_model_key()
        if model_key in related._baked_results:
            setattr(model, related.to_attr, related._baked_results[model_key])
        else:
            clauses = []
            for pkcol in cls.pkcolumns:
                clauses.append(getattr(model.table.columns, pkcol) == getattr(row, pkcol))
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
            queries.append(cls.__set_prefetch(row=row, model=model, related=related))
        if queries:
            await asyncio.gather(*queries)
