import asyncio
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Sequence, Type, Union, cast

from sqlalchemy.engine.result import Row

from edgy.core.db.models.base import EdgyBaseModel
from edgy.exceptions import QuerySetError

if TYPE_CHECKING:  # pragma: no cover
    from edgy import Model, Prefetch, QuerySet


class ModelRow(EdgyBaseModel):
    """
    Builds a row for a specific model
    """

    @classmethod
    def from_sqla_row(
        cls,
        row: Row,
        select_related: Optional[Sequence[Any]] = None,
        prefetch_related: Optional[Sequence["Prefetch"]] = None,
        is_only_fields: bool = False,
        only_fields: Sequence[str] = None,
        is_defer_fields: bool = False,
        exclude_secrets: bool = False,
        using_schema: Union[str, None] = None,
    ) -> Optional[Type["Model"]]:
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
            if "__" in related:
                first_part, remainder = related.split("__", 1)
                try:
                    model_cls = cls.meta.fields_mapping[first_part].target
                except KeyError:
                    model_cls = cls.meta.related_fields[first_part].related_from

                item[first_part] = model_cls.from_sqla_row(
                    row,
                    select_related=[remainder],
                    prefetch_related=prefetch_related,
                    exclude_secrets=exclude_secrets,
                    using_schema=using_schema,
                )
            else:
                try:
                    model_cls = cls.meta.fields_mapping[related].target
                except KeyError:
                    model_cls = cls.meta.related_fields[related].related_from
                item[related] = model_cls.from_sqla_row(row, exclude_secrets=exclude_secrets, using_schema=using_schema)

        # Populate the related names
        # Making sure if the model being queried is not inside a select related
        # This way it is not overritten by any value
        for related, foreign_key in cls.meta.foreign_key_fields.items():
            ignore_related: bool = cls.__should_ignore_related_name(related, select_related)
            if ignore_related:
                continue

            model_related = foreign_key.target

            # Apply the schema to the model
            model_related = cls.__apply_schema(model_related, using_schema)

            child_item = {}
            for column in model_related.table.columns:
                if column.name in secret_fields or related in secret_fields:
                    continue
                if column.name not in cls.fields.keys():
                    continue
                elif related not in child_item:
                    if row[related] is not None:
                        child_item[column.name] = row[related]

            # Make sure we generate a temporary reduced model
            # For the related fields. We simply chnage the structure of the model
            # and rebuild it with the new fields.
            if related not in secret_fields:
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
            model = cast("Type[Model]", cls.proxy_model(**item))

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
            cast("Type[Model]", cls(**item)) if not exclude_secrets else cast("Type[Model]", cls.proxy_model(**item))
        )

        # Apply the schema to the model
        model = cls.__apply_schema(model, using_schema)

        # Handle prefetch related fields.
        model = cls.__handle_prefetch_related(row=row, model=model, prefetch_related=prefetch_related)
        return model

    @classmethod
    def __apply_schema(cls, model: Type["Model"], schema: Optional[str] = None) -> Type["Model"]:
        # Apply the schema to the model
        if schema is not None:
            model.table = model.build(schema)  # type: ignore
            model.proxy_model.table = model.proxy_model.build(schema)  # type: ignore
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

    @classmethod
    def __handle_prefetch_related(
        cls,
        row: Row,
        model: Type["Model"],
        # for advancing
        prefetch_related: Sequence["Prefetch"],
        parent_cls: Optional[Type["Model"]] = None,
        # for going back
        inverse_path: str = "",
        is_nested: bool = False,
    ) -> Type["Model"]:
        """
        Handles any prefetch related scenario from the model.
        Loads in advance all the models needed for a specific record

        Recursively checks for the related field and validates if there is any conflicting
        attribute. If there is, a `QuerySetError` is raised.
        """
        if not parent_cls:
            parent_cls = model

        for related in prefetch_related:
            if not is_nested:
                # Check for conflicting names
                # If to_attr has the same name of any
                if hasattr(parent_cls, related.to_attr):
                    raise QuerySetError(
                        f"Conflicting attribute to_attr='{related.related_name}' with '{related.to_attr}' in {parent_cls.__class__.__name__}"
                    )

            if not is_nested:
                inverse_path = ""

            if "__" in related.related_name:
                first_part, remainder = related.related_name.split("__", 1)

                try:
                    model_cls = cls.meta.related_fields[first_part].related_from
                    reverse_part = cls.meta.related_fields[first_part].foreign_key_name
                except KeyError:
                    model_cls = cls.meta.foreign_key_fields[first_part].target
                    reverse_part = cls.meta.foreign_key_fields[first_part].related_name

                # Build the new nested Prefetch object
                remainder_prefetch = related.__class__(
                    related_name=remainder, to_attr=related.to_attr, queryset=related.queryset
                )
                if inverse_path:
                    inverse_path = f"{reverse_part}__{inverse_path}"
                else:
                    inverse_path = reverse_part

                # Recursively continue the process of handling the
                # new prefetch
                model_cls.__handle_prefetch_related(
                    row,
                    model,
                    prefetch_related=[remainder_prefetch],
                    inverse_path=inverse_path,
                    parent_cls=model,
                    is_nested=True,
                )

            # Check for individual not nested querysets
            elif related.queryset is not None and not is_nested:
                extra = {}
                for pkname in cls.pknames:
                    filter_by_pk = row[pkname]
                    extra[f"{related.related_name}__{pkname}"] = filter_by_pk
                related.queryset.extra = extra

                # Execute the queryset
                records = asyncio.get_event_loop().run_until_complete(cls.run_query(queryset=related.queryset))
                setattr(model, related.to_attr, records)
            else:
                records = cls.process_nested_prefetch_related(
                    row,
                    prefetch_related=related,
                    inverse_path=inverse_path,
                    parent_cls=model,
                    queryset=related.queryset,
                )

                setattr(model, related.to_attr, records)
        return model

    @classmethod
    def process_nested_prefetch_related(
        cls,
        row: Row,
        prefetch_related: "Prefetch",
        parent_cls: Type["Model"],
        inverse_path: str,
        queryset: "QuerySet",
    ) -> List[Type["Model"]]:
        """
        Processes the nested prefetch related names.
        """
        # Get the related field
        try:
            related_field = cls.meta.related_fields[prefetch_related.related_name]
            reverse_part = cls.meta.related_fields[prefetch_related.related_name].foreign_key_name
        except KeyError:
            fk_field = cls.meta.foreign_key_fields[prefetch_related.related_name]
            reverse_part = fk_field.related_name
            related_field = fk_field.target.meta.related_fields[fk_field.related_name]

        if inverse_path:
            inverse_path = f"{reverse_part}__{inverse_path}"
        else:
            inverse_path = reverse_part

        # Get the model to query related
        model_class = related_field.related_from

        # TODO: related_field.clean would be better
        # fix this later when allowing selecting fields for fireign keys
        # Extract foreign key value
        extra = {}
        for pkname in parent_cls.pknames:
            filter_by_pk = row[pkname]
            extra[f"{inverse_path}__{pkname}"] = filter_by_pk

        records = asyncio.get_event_loop().run_until_complete(cls.run_query(model_class, extra, queryset))
        return records

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
            queryset.extra = extra

        return await queryset
