from functools import cached_property
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional, Sequence, Tuple, TypeVar

import sqlalchemy
from pydantic import BaseModel

from edgy.core.db.fields.base import BaseField, BaseForeignKey
from edgy.core.db.fields.factories import ForeignKeyFieldFactory
from edgy.core.db.relationships.relation import SingleRelation
from edgy.core.terminal import Print
from edgy.protocols.many_relationship import ManyRelationProtocol

if TYPE_CHECKING:
    from edgy import Model


T = TypeVar("T", bound="Model")

terminal = Print()


FK_CHAR_LIMIT = 63


def _removeprefix(text: str, prefix: str) -> str:
    # TODO: replace with removeprefix when python3.9 is minimum
    if text.startswith(prefix):
        return text[len(prefix) :]
    else:
        return text


class BaseForeignKeyField(BaseForeignKey):
    def __init__(
        self,
        *,
        on_update: str,
        on_delete: str,
        related_fields: Sequence[str] = (),
        no_constraint: bool = False,
        embed_parent: Optional[Tuple[str, str]]=None,
        relation_fn: Optional[Callable[..., ManyRelationProtocol]]=None,
        reverse_path_fn: Optional[Callable[[str], Tuple[Any, str, str]]]=None,
        **kwargs: Any,
    ) -> None:
        self.related_fields = related_fields
        self.on_update = on_update
        self.on_delete = on_delete
        self.no_constraint = no_constraint
        self.embed_parent = embed_parent
        self.relation_fn =relation_fn
        self.reverse_path_fn = reverse_path_fn
        super().__init__(**kwargs)

    def get_relation(self, **kwargs: Any) -> ManyRelationProtocol:
        if self.relation_fn is not None:
            return self.relation_fn(**kwargs)
        return SingleRelation(to=self.owner, to_foreign_key=self.name, embed_parent=self.embed_parent, **kwargs)

    def traverse_field(self, path: str) -> Tuple[Any, str, str]:
        return self.target, self.reverse_name, _removeprefix(_removeprefix(path, self.name), "__")

    def reverse_traverse_field(self, path: str) -> Tuple[Any, str, str]:
        if self.reverse_path_fn:
            return self.reverse_path_fn(path)
        return self.owner, self.name, _removeprefix(_removeprefix(path, self.reverse_name), "__")

    @cached_property
    def related_columns(self) -> Dict[str, Optional[sqlalchemy.Column]]:
        target = self.target
        columns: Dict[str, Optional[sqlalchemy.Column]] = {}
        if self.related_fields:
            for field_name in self.related_fields:
                if field_name in target.meta.fields_mapping:
                    for column in target.meta.field_to_columns[field_name]:
                        columns[column.key] = column
                else:
                    # placeholder for extracting column
                    columns[field_name] = None
        else:
            # try to use explicit primary keys
            if target.pknames:
                for pkname in target.pknames:
                    for column in target.meta.field_to_columns[pkname]:
                        columns[column.key] = column
            elif target.pkcolumns:
                # placeholder for extracting column
                # WARNING: this can recursively loop
                columns = {col: None for col in target.pkcolumns}
        return columns

    def expand_relationship(self, value: Any) -> Any:
        target = self.target

        if isinstance(value, (target, target.proxy_model)):
            return value
        related_columns = self.related_columns.keys()
        if len(related_columns) == 1 and not isinstance(value, (dict, BaseModel)):
            value = {next(iter(related_columns)): value}
        elif isinstance(value, BaseModel):
            return self.expand_relationship({col: getattr(value, col) for col in related_columns})
        elif value is None:
            return None
        instance = target.proxy_model(**value)
        instance.identifying_db_fields = related_columns
        if not instance.can_load:
            return None
        return instance

    def clean(self, name: str, value: Any, for_query: bool = False) -> Dict[str, Any]:
        retdict: Dict[str, Any] = {}
        column_names = self.owner.meta.field_to_column_names[name]
        assert len(column_names) >= 1
        if value is None:
            for column_name in column_names:
                retdict[column_name] = None
        elif isinstance(value, dict):
            for column_name in column_names:
                translated_name = self.from_fk_field_name(name, column_name)
                if translated_name in value:
                    retdict[column_name] = value[translated_name]
        elif isinstance(value, BaseModel):
            for column_name in column_names:
                translated_name = self.from_fk_field_name(name, column_name)
                if hasattr(value, translated_name):
                    retdict[column_name] = getattr(value, translated_name)
        elif len(column_names) == 1:
            column_name = next(iter(column_names))
            retdict[column_name] = value
        else:
            raise ValueError(f"cannot handle: {value} of type {type(value)}")
        return retdict

    def modify_input(self, name: str, kwargs: Dict[str, Any]) -> None:
        column_names = self.get_column_names(name)
        assert len(column_names) >= 1
        if len(column_names) == 1:
            return
        to_add = {}
        # for idempotency
        for column_name in column_names:
            if column_name in kwargs:
                to_add[self.from_fk_field_name(name, column_name)] = kwargs.pop(column_name)
        # empty
        if not to_add:
            return
        if name in kwargs:
            raise ValueError("Cannot specify a foreign key column and the foreign key itself")
        if len(column_names) != len(to_add):
            raise ValueError("Cannot update the foreign key partially")
        kwargs[name] = to_add

    def get_fk_name(self, name: str) -> str:
        """
        Builds the fk name for the engine.

        Engines have a limitation of the foreign key being bigger than 63
        characters.

        if that happens, we need to assure it is small.
        """
        fk_name = f"fk_{self.owner.meta.tablename}_{self.target.meta.tablename}_{name}"
        if not len(fk_name) > FK_CHAR_LIMIT:
            return fk_name
        return fk_name[:FK_CHAR_LIMIT]

    def get_fkindex_name(self, name: str) -> str:
        """
        Builds the fk name for the engine.

        Engines have a limitation of the foreign key being bigger than 63
        characters.

        if that happens, we need to assure it is small.
        """
        fk_name = f"fkindex_{self.owner.meta.tablename}_{self.target.meta.tablename}_{name}"
        if not len(fk_name) > FK_CHAR_LIMIT:
            return fk_name
        return fk_name[:FK_CHAR_LIMIT]

    def get_fk_field_name(self, name: str, fieldname: str) -> str:
        if len(self.related_columns) == 1:
            return name
        return f"{name}_{fieldname}"

    def from_fk_field_name(self, name: str, fieldname: str) -> str:
        if len(self.related_columns) == 1:
            return next(iter(self.related_columns.keys()))
        return _removeprefix(fieldname, f"{name}_")

    def get_columns(self, name: str) -> Sequence[sqlalchemy.Column]:
        target = self.target
        columns = []
        for column_name, related_column in self.related_columns.items():
            if related_column is None:
                related_column = target.table.columns[column_name]
            fkcolumn_name = self.get_fk_field_name(name, column_name)
            # use the related column as reference
            fkcolumn = sqlalchemy.Column(
                fkcolumn_name,
                related_column.type,
                primary_key=self.primary_key,
                autoincrement=False,
                nullable=related_column.nullable or self.null,
                unique=related_column.unique,
            )
            columns.append(fkcolumn)
        return columns

    def get_global_constraints(self, name: str, columns: Sequence[sqlalchemy.Column]) -> Sequence[sqlalchemy.Constraint]:
        constraints = []
        no_constraint = self.no_constraint
        if self.is_cross_db():
            no_constraint = True
        if not no_constraint:
            target = self.target
            constraints.append(
                sqlalchemy.ForeignKeyConstraint(
                    columns,
                    [f"{target.meta.tablename}.{self.from_fk_field_name(name, column.key)}" for column in columns],
                    ondelete=self.on_delete,
                    onupdate=self.on_update,
                    name=self.get_fk_name(name),
                ),
            )
        # set for unique or if index is True
        if self.unique or self.index:
            constraints.append(
                sqlalchemy.Index(
                    self.get_fkindex_name(name), *columns, unique=self.unique
                ),
            )

        return constraints



class ForeignKey(ForeignKeyFieldFactory):
    _bases = (BaseForeignKeyField,)
    _type: Any = Any

    def __new__(  # type: ignore
        cls,
        to: "Model",
        **kwargs: Any,
    ) -> BaseField:
        return super().__new__(cls, to=to, **kwargs)
