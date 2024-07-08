import asyncio
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Sequence, Type, Union, cast

from edgy.core.db.fields.base import RelationshipField
from edgy.core.db.models.base import EdgyBaseModel
from edgy.core.db.relationships.utils import crawl_relationship
from edgy.core.utils.sync import run_sync
from edgy.exceptions import QuerySetError

if TYPE_CHECKING:  # pragma: no cover
    from sqlalchemy.engine.result import Row

    from edgy import Model, Prefetch, QuerySet


class ModelRow(EdgyBaseModel):
    """
    Builds a row for a specific model
    """

    class Meta:
        abstract = True

    @classmethod
    def from_sqla_row(
        cls,
        row: "Row",
        select_related: Optional[Sequence[Any]] = None,
        prefetch_related: Optional[Sequence["Prefetch"]] = None,
        is_only_fields: bool = False,
        only_fields: Sequence[str] = None,
        is_defer_fields: bool = False,
        exclude_secrets: bool = False,
        using_schema: Union[str, None] = None,
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
        item: Dict[str, Any] = {}
        select_related = select_related or []
        prefetch_related = prefetch_related or []
        secret_fields = [name for name, field in cls.fields.items() if field.secret] if exclude_secrets else []

        for related in select_related:
            field_name = related.split("__", 1)[0]
            try:
                field = cls.meta.fields_mapping[field_name]
            except KeyError:
                raise QuerySetError(
                    detail=f"Selected field \"{field_name}\" does not exist on {cls}."
                ) from None
            if isinstance(field, RelationshipField):
                model_class, _, remainder = field.traverse_field(related)
            else:
                raise QuerySetError(
                    detail=f"Selected field \"{field_name}\" is not a RelationshipField on {cls}."
                ) from None
            if remainder:
                item[field_name] = model_class.from_sqla_row(
                    row,
                    select_related=[remainder],
                    prefetch_related=prefetch_related,
                    exclude_secrets=exclude_secrets,
                    using_schema=using_schema,
                )
            else:
                item[field_name] = model_class.from_sqla_row(row, exclude_secrets=exclude_secrets, using_schema=using_schema)
        # Populate the related names
        # Making sure if the model being queried is not inside a select related
        # This way it is not overritten by any value
        for related, foreign_key in cls.meta.foreign_key_fields.items():
            ignore_related: bool = cls.__should_ignore_related_name(related, select_related)
            if ignore_related or related in secret_fields:
                continue

            columns_to_check = foreign_key.get_column_names(related)
            if secret_fields and not columns_to_check.isdisjoint(secret_fields):
                continue

            model_related = foreign_key.target

            # Apply the schema to the model
            model_related = cls.__apply_schema(model_related, using_schema)

            child_item = {}
            for column_name in columns_to_check:
                if column_name not in row:
                    continue
                elif row[column_name] is not None:  # type: ignore
                    child_item[foreign_key.from_fk_field_name(related, column_name)] = row[column_name]  # type: ignore

            # Make sure we generate a temporary reduced model
            # For the related fields. We simply chnage the structure of the model
            # and rebuild it with the new fields.
            item[related] = model_related.proxy_model(**child_item)

        # Check for the only_fields
        if is_only_fields or is_defer_fields:
            mapping_fields = (
                [str(field) for field in only_fields] if is_only_fields else list(row.keys())  # type: ignore
            )

            for column, value in row._mapping.items():
                if column in secret_fields:
                    continue
                # Making sure when a table is reflected, maps the right fields of the ReflectModel
                if column not in mapping_fields:
                    continue

                if column not in item:
                    item[column] = value

            # We need to generify the model fields to make sure we can populate the
            # model without mandatory fields
            model = cast("Model", cls.proxy_model(**item))

            # Apply the schema to the model
            model = cls.__apply_schema(model, using_schema)

            model = cls.__handle_prefetch_related(row=row, model=model, prefetch_related=prefetch_related)
            return model
        else:
            # Pull out the regular column values.
            for column in cls.table.columns:
                # Making sure when a table is reflected, maps the right fields of the ReflectModel
                if column.name in secret_fields:
                    continue
                if column.name not in cls.fields.keys():
                    continue
                elif column.name not in item:
                    item[column.name] = row[column]

        model = (
            cast("Model", cls(**item)) if not exclude_secrets else cast("Model", cls.proxy_model(**item))
        )

        # Apply the schema to the model
        model = cls.__apply_schema(model, using_schema)

        # Handle prefetch related fields.
        model = cls.__handle_prefetch_related(row=row, model=model, prefetch_related=prefetch_related)
        return model

    @classmethod
    def __apply_schema(cls, model: "Model", schema: Optional[str] = None) -> "Model":
        # Apply the schema to the model
        if schema is not None:
            model.table = model.build(schema)
            model.proxy_model.table = model.proxy_model.build(schema)
        return model

    @classmethod
    def __should_ignore_related_name(cls, related_name: str, select_related: Sequence[str]) -> bool:
        """
        Validates if it should populate the related field if select related is not considered.
        """
        for related_field in select_related:
            fields = related_field.split("__")
            if related_name in fields:
                return True
        return False


    @staticmethod
    def __check_prefetch_collision(model: "Model", related: "Prefetch") -> None:
        if hasattr(model, related.to_attr) or related.to_attr in model.meta.fields_mapping or related.to_attr in model.meta.managers:
            raise QuerySetError(
                f"Conflicting attribute to_attr='{related.related_name}' with '{related.to_attr}' in {model.__class__.__name__}"
            )

    @classmethod
    async def __set_prefetch(cls, row: "Row", model: "Model", related: "Prefetch") -> None:
        cls.__check_prefetch_collision(model, related)
        clauses = []
        for pkcol in cls.pkcolumns:
            clauses.append(getattr(model.table.columns, pkcol) == row[pkcol])
        queryset = related.queryset
        crawl_result = crawl_relationship(model.__class__, related.related_name, traverse_last=True)
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
    def __handle_prefetch_related(
        cls,
        row: "Row",
        model: "Model",
        prefetch_related: Sequence["Prefetch"],
    ) -> "Model":
        """
        Handles any prefetch related scenario from the model.
        Loads in advance all the models needed for a specific record

        Recursively checks for the related field and validates if there is any conflicting
        attribute. If there is, a `QuerySetError` is raised.
        """

        queries = []

        for related in prefetch_related:

            # Check for conflicting names
            # If to_attr has the same name of any
            cls.__check_prefetch_collision(model=model, related=related)
            queries.append(cls.__set_prefetch(row=row, model=model, related=related))
        run_sync(asyncio.gather(*queries))
        return model

    @classmethod
    async def run_query(
        cls,
        model: Optional[Type["Model"]] = None,
        extra: Optional[Dict[str, Any]] = None,
        queryset: Optional["QuerySet"] = None,
    ) -> Union[List[Type["Model"]], Any]:
        """
        Runs a specific query against a given model with filters.
        """

        if not queryset:
            return await model.query.filter(**extra)  # type: ignore

        if extra:
            queryset = queryset.filter(**extra)

        return await queryset
