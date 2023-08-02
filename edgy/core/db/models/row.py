from typing import TYPE_CHECKING, Any, Dict, Optional, Sequence, Type

from sqlalchemy.engine.result import Row

from edgy.core.db.models.base import EdgyBaseModel

if TYPE_CHECKING:  # pragma: no cover
    from edgy import Model


class ModelRow(EdgyBaseModel):
    """
    Builds a row for a specific model
    """

    @classmethod
    def from_sqla_row(
        cls, row: Row, select_related: Optional[Sequence[Any]] = None
    ) -> Optional[Type["Model"]]:
        """
        Class method to convert a SQLAlchemy Row result into a EdgyModel row type.
        """
        item: Dict[str, Any] = {}
        select_related = select_related or []

        for related in select_related:
            if "__" in related:
                first_part, remainder = related.split("__", 1)
                try:
                    model_cls = cls.fields[first_part].target
                except KeyError:
                    model_cls = getattr(cls, first_part).related_from
                item[first_part] = model_cls.from_sqla_row(row, select_related=[remainder])
            else:
                try:
                    model_cls = cls.fields[related].target
                except KeyError:
                    model_cls = getattr(cls, related).related_from
                item[related] = model_cls.from_sqla_row(row)

        # Pull out the regular column values.
        for column in cls.table.columns:
            # Making sure when a table is reflected, maps the right fields of the ReflectModel
            if column.name not in cls.fields.keys():
                continue

            elif column.name not in item:
                item[column.name] = row[column]

        item = cls.populate_nested_models_from_row(
            item=item, row=row, related_names=cls.meta.foreign_key_fields
        )
        return cls(**item)

    @classmethod
    def populate_nested_models_from_row(
        cls,
        item: Dict[str, Any],
        row: Row,
        related_names: Dict[str, Any],
        select_related: Optional[Sequence[Any]] = None,
    ) -> Dict[Any, Any]:
        """
        Populates the database model with the nested results from the row.
        Transverses all the related names inside of a given model and obtains the instance needed
        to be generated.

        The related names are the representation of any SQLAlchemy ForeignKey.
        """
        if not related_names:
            return item

        select_related = select_related or []

        for related, foreign_key in related_names.items():
            model_child = foreign_key.target
            child_item = {}

            for related in select_related:
                if "__" in related:
                    first_part, remainder = related.split("__", 1)
                    try:
                        model_child = cls.fields[first_part].target
                    except KeyError:
                        model_child = getattr(cls, first_part).related_from
                    item[first_part] = model_child.from_sqla_row(row, select_related=[remainder])
                else:
                    try:
                        model_child = model_child.fields[related].target
                    except KeyError:
                        model_child = getattr(cls, related).related_from
                    item[related] = model_child.from_sqla_row(row)

            for column in cls.table.columns:
                if column.name not in model_child.fields.keys():
                    continue
                elif related not in child_item:
                    child_item[column.name] = row[related]

            child = model_child(**child_item)
            item[related] = child

        return item
