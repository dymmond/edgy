from functools import cached_property
from typing import TYPE_CHECKING, Any, Dict, FrozenSet, Optional, Sequence, TypeVar

import sqlalchemy
from pydantic import BaseModel

from edgy.core.db.fields.base import BaseField, BaseForeignKey
from edgy.core.db.fields.core import ForeignKeyFieldFactory
from edgy.core.terminal import Print

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
        **kwargs: Any,
    ) -> None:
        self.related_fields = related_fields
        self.on_update = on_update
        self.on_delete = on_delete
        super().__init__(**kwargs)

    @cached_property
    def related_columns(self) -> Dict[str, Optional[sqlalchemy.Column]]:
        target = self.target
        columns: Dict[str, Optional[sqlalchemy.Column]] = {}
        if self.related_fields:
            for field_name in self.related_fields:
                if field_name in target.meta.fields_mapping:
                    for column in target.meta.fields_mapping[field_name].get_columns(field_name):
                        columns[column.key] = column
                else:
                    columns[field_name] = None
        else:
            # try to use explicit primary keys
            if target.pknames:
                for pkname in target.pknames:
                    for column in target.meta.fields_mapping[pkname].get_columns(pkname):
                        columns[column.key] = column
            elif target.pkcolumns:
                columns.update({col: None for col in target.pkcolumns})
        return columns

    def expand_relationship(self, value: Any) -> Any:
        target = self.target

        if isinstance(value, (target, target.proxy_model)):
            return value
        return target.proxy_model(pk=value)

    def clean(self, name: str, value: Any) -> Dict[str, Any]:
        target = self.target
        retdict: Dict[str, Any] = {}
        if value is None:
            for column_name in self.get_column_names(name):
                retdict[column_name] = None
        elif isinstance(value, dict):
            for pkname in target.pknames:
                if pkname in value:
                    retdict.update(target.meta.fields_mapping[pkname].clean(self.get_fk_field_name(name, pkname), value[pkname]))
        elif isinstance(value, BaseModel):
            for pkname in target.pknames:
                if hasattr(value, pkname):
                    retdict.update(
                        target.meta.fields_mapping[pkname].clean(self.get_fk_field_name(name, pkname), getattr(value, pkname))
                    )
        elif len(target.pknames) == 1:
            retdict.update(
                target.meta.fields_mapping[target.pknames[0]].clean(self.get_fk_field_name(name, target.pknames[0]), value)
            )
        else:
            raise ValueError(f"cannot handle: {value} of type {type(value)}")
        return retdict

    def modify_input(self, name: str, kwargs: Dict[str, Any]) -> None:
        if len(self.target.pknames) == 1:
            return
        to_add = {}
        # for idempotency
        for column_name in self.get_column_names(name):
            if column_name in kwargs:
                to_add[self.from_fk_field_name(name, column_name)] = kwargs.pop(column_name)
        # empty
        if not to_add:
            return
        if name in kwargs:
            raise ValueError("Cannot specify a foreign key column and the foreign key itself")
        if len(self.target.pknames) != len(to_add):
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

    def get_fk_field_name(self, name: str, fieldname: str) -> str:
        target = self.target
        if len(target.pknames) == 1:
            return name
        return f"{name}_{fieldname}"

    def from_fk_field_name(self, name: str, fieldname: str) -> str:
        target = self.target
        if len(target.pknames) == 1:
            return target.pknames[0]  # type: ignore
        return _removeprefix(fieldname, f"{name}_")

    def get_column_names(self, name: str) -> FrozenSet[str]:
        if not hasattr(self, "_column_names") or name != self.name:
            column_names = set()
            for column in self.owner.meta.field_to_columns[name]:
                column_names.add(column.name)
            if name != self.name:
                return frozenset(column_names)
            self._column_names = frozenset(column_names)
        return self._column_names

    def get_columns(self, name: str) -> Sequence[sqlalchemy.Column]:
        target = self.target
        columns = []
        for column_name, pkcolumn in self.related_columns.items():
            if pkcolumn is None:
                pkcolumn = target.table.columns[column_name]
            fkcolumn_name = self.get_fk_field_name(name, column_name)
            fkcolumn = sqlalchemy.Column(
                fkcolumn_name,
                pkcolumn.type,
                primary_key=self.primary_key,
                autoincrement=False,
                nullable=pkcolumn.nullable or self.null,
                unique=pkcolumn.unique,
            )
            columns.append(fkcolumn)
        return columns

    def get_global_constraints(self, name: str, columns: Sequence[sqlalchemy.Column]) -> Sequence[sqlalchemy.Constraint]:
        target = self.target
        return [
            sqlalchemy.ForeignKeyConstraint(
                columns,
                [f"{target.meta.tablename}.{self.from_fk_field_name(name, column.key)}" for column in columns],
                ondelete=self.on_delete,
                onupdate=self.on_update,
                name=self.get_fk_name(name),
            ),
        ]



class ForeignKey(ForeignKeyFieldFactory):
    _bases = (BaseForeignKeyField,)
    _type: Any = Any

    def __new__(  # type: ignore
        cls,
        to: "Model",
        **kwargs: Any,
    ) -> BaseField:
        return super().__new__(cls, to=to, **kwargs)
