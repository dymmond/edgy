import asyncio
from typing import TYPE_CHECKING, Any, Dict, Optional, Sequence, Type, cast

from sqlalchemy.engine.result import Row

from edgy.core.db.models.base import EdgyBaseModel

if TYPE_CHECKING:  # pragma: no cover
    from edgy import Model, Prefetch


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

        for related in select_related:
            if "__" in related:
                first_part, remainder = related.split("__", 1)
                try:
                    model_cls = cls.fields[first_part].target
                except KeyError:
                    model_cls = getattr(cls, first_part).related_from
                item[first_part] = model_cls.from_sqla_row(
                    row, select_related=[remainder], prefetch_related=prefetch_related
                )
            else:
                try:
                    model_cls = cls.fields[related].target
                except KeyError:
                    model_cls = getattr(cls, related).related_from
                item[related] = model_cls.from_sqla_row(row)

        # Populate the related names
        # Making sure if the model being queried is not inside a select related
        # This way it is not overritten by any value
        for related, foreign_key in cls.meta.foreign_key_fields.items():
            ignore_related: bool = cls.should_ignore_related_name(related, select_related)
            if ignore_related:
                continue

            model_related = foreign_key.target
            child_item = {}

            for column in model_related.table.columns:
                if column.name not in cls.fields.keys():
                    continue
                elif related not in child_item:
                    if row[related] is not None:
                        child_item[column.name] = row[related]

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
                # Making sure when a table is reflected, maps the right fields of the ReflectModel
                if column not in mapping_fields:
                    continue

                if column not in item:
                    item[column] = value

            # We need to generify the model fields to make sure we can populate the
            # model without mandatory fields
            model = cast("Type[Model]", cls.proxy_model(**item))
            model = cls.handle_prefetch_related(
                row=row, model=model, prefetch_related=prefetch_related
            )
            return model
        else:
            # Pull out the regular column values.
            for column in cls.table.columns:
                # Making sure when a table is reflected, maps the right fields of the ReflectModel
                if column.name not in cls.fields.keys():
                    continue
                elif column.name not in item:
                    item[column.name] = row[column]

        model = cast("Type[Model]", cls(**item))
        model = cls.handle_prefetch_related(
            row=row, model=model, prefetch_related=prefetch_related
        )
        return model

    @classmethod
    def should_ignore_related_name(cls, related_name: str, select_related: Sequence[str]) -> bool:
        """
        Validates if it should populate the related field if select related is not considered.
        """
        for related_field in select_related:
            fields = related_field.split("__")
            if related_name in fields:
                return True
        return False

    @classmethod
    def handle_prefetch_related(
        cls, row: Row, model: Type["Model"], prefetch_related: Sequence["Prefetch"]
    ) -> Type["Model"]:
        """
        Handles any prefetch related scenario from the model.

        Loads in advance all the models needed for a specific record
        """
        for prefetch in prefetch_related:
            # Validates the queryset

            if hasattr(cls, prefetch.to_attr):
                raise ValueError(f"Confliting `{prefetch.to_attr}` in {cls.__name__}")

            if prefetch.related_name not in cls.meta.related_fields:
                raise ValueError(f"'{prefetch.related_name}' has not been created or declared.")

            if prefetch.queryset is not None:
                filter_by_pk = row[cls.pkname]
                extra = {f"{prefetch.related_name}__id": filter_by_pk}
                prefetch.queryset.extra = extra

                records = asyncio.get_event_loop().run_until_complete(prefetch.queryset)
                setattr(model, prefetch.to_attr, records)

            # elif "__" in prefetch.related_name:
            #     first_part, remainder = related.split("__", 1)
        return model
