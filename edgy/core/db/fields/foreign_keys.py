from functools import cached_property
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional, Sequence, Tuple, Union, cast

import sqlalchemy
from pydantic import BaseModel

from edgy.core.db.constants import CASCADE
from edgy.core.db.fields.base import BaseForeignKey
from edgy.core.db.fields.factories import ForeignKeyFieldFactory
from edgy.core.db.fields.types import BaseFieldType
from edgy.core.db.relationships.relation import (
    SingleRelation,
    VirtualCascadeDeletionSingleRelation,
)
from edgy.exceptions import FieldDefinitionError
from edgy.protocols.many_relationship import ManyRelationProtocol

if TYPE_CHECKING:
    from edgy.core.db.models.types import BaseModelType


FK_CHAR_LIMIT = 63


def _removeprefix(text: str, prefix: str) -> str:
    # TODO: replace with removeprefix when python3.9 is minimum
    if text.startswith(prefix):
        return text[len(prefix) :]
    else:
        return text


class BaseForeignKeyField(BaseForeignKey):
    force_cascade_deletion_relation: bool = False
    relation_has_post_delete_callback: bool = False

    def __init__(
        self,
        *,
        on_update: str,
        on_delete: str,
        related_fields: Sequence[str] = (),
        no_constraint: bool = False,
        embed_parent: Optional[Tuple[str, str]] = None,
        relation_fn: Optional[Callable[..., ManyRelationProtocol]] = None,
        reverse_path_fn: Optional[Callable[[str], Tuple[Any, str, str]]] = None,
        remove_referenced: bool = False,
        **kwargs: Any,
    ) -> None:
        self.related_fields = related_fields
        self.on_update = on_update
        self.on_delete = on_delete
        self.no_constraint = no_constraint
        self.embed_parent = embed_parent
        self.relation_fn = relation_fn
        self.reverse_path_fn = reverse_path_fn
        self.remove_referenced = remove_referenced
        if remove_referenced:
            self.post_delete_callback = self._notset_post_delete_callback
        super().__init__(**kwargs)
        if self.force_cascade_deletion_relation or (
            self.on_delete == CASCADE and self.no_constraint
        ):
            self.relation_has_post_delete_callback = True

    async def _notset_post_delete_callback(self, value: Any, instance: "BaseModelType") -> None:
        value = self.expand_relationship(value)
        if value is not None:
            await value.delete(remove_referenced_call=True)

    async def pre_save_callback(
        self, value: Any, original_value: Any, force_insert: bool, instance: "BaseModelType"
    ) -> Any:
        target = self.target
        if value is None or (isinstance(value, dict) and not value):
            value = original_value
        # e.g. default was a Model
        if isinstance(value, (target, target.proxy_model)):
            await value.save(force_insert=force_insert)
            return self.clean(self.name, value, for_query=False)
        elif isinstance(value, dict):
            return await self.pre_save_callback(
                target(**value), None, force_insert=force_insert, instance=instance
            )
        return {self.name: value}

    def get_relation(self, **kwargs: Any) -> ManyRelationProtocol:
        if self.relation_fn is not None:
            return self.relation_fn(**kwargs)
        if self.force_cascade_deletion_relation or (
            self.on_delete == CASCADE and self.no_constraint
        ):
            relation: Any = VirtualCascadeDeletionSingleRelation
        else:
            relation = SingleRelation
        return cast(
            ManyRelationProtocol,
            relation(
                to=self.owner, to_foreign_key=self.name, embed_parent=self.embed_parent, **kwargs
            ),
        )

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
                if field_name in target.meta.fields:
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

    def modify_input(self, name: str, kwargs: Dict[str, Any], phase: str = "") -> None:
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
            # after removing the attributes return
            return
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

    def get_global_constraints(
        self,
        name: str,
        columns: Sequence[sqlalchemy.Column],
        schemes: Sequence[str] = (),
        no_constraint: Optional[bool] = None,
    ) -> Sequence[sqlalchemy.Constraint]:
        constraints = []
        no_constraint = bool(no_constraint or self.no_constraint or self.is_cross_db())
        if not no_constraint:
            target = self.target
            assert not target.__is_proxy_model__
            # use the last prefix as fallback
            prefix = ""
            for schema in schemes:
                prefix = f"{schema}.{target.meta.tablename}" if schema else target.meta.tablename
                if prefix in target.meta.registry.metadata.tables:
                    break
            constraints.append(
                sqlalchemy.ForeignKeyConstraint(
                    columns,
                    [
                        f"{prefix}.{self.from_fk_field_name(name, column.key)}"
                        for column in columns
                    ],
                    ondelete=self.on_delete,
                    onupdate=self.on_update,
                    name=self.get_fk_name(name),
                ),
            )
        # set for unique or if index is True
        if self.unique or self.index:
            constraints.append(
                sqlalchemy.Index(self.get_fkindex_name(name), *columns, unique=self.unique),
            )

        return constraints


class ForeignKey(ForeignKeyFieldFactory):
    field_bases = (BaseForeignKeyField,)
    field_type: Any = Any

    def __new__(  # type: ignore
        cls,
        to: Union["BaseModelType", str],
        **kwargs: Any,
    ) -> BaseFieldType:
        return super().__new__(cls, to=to, **kwargs)

    @classmethod
    def validate(cls, kwargs: Dict[str, Any]) -> None:
        super().validate(kwargs)
        embed_parent = kwargs.get("embed_parent")
        if embed_parent and "__" in embed_parent[1]:
            raise FieldDefinitionError(
                '"embed_parent" second argument (for embedding parent) cannot contain "__".'
            )
