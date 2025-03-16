from collections.abc import Sequence
from functools import cached_property
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Optional,
    Union,
    cast,
)

import sqlalchemy
from pydantic import BaseModel

from edgy.core.db.constants import SET_DEFAULT, SET_NULL
from edgy.core.db.context_vars import CURRENT_PHASE
from edgy.core.db.fields.base import BaseForeignKey
from edgy.core.db.fields.factories import ForeignKeyFieldFactory
from edgy.core.db.fields.types import BaseFieldType
from edgy.core.db.relationships.relation import (
    SingleRelation,
    VirtualCascadeDeletionSingleRelation,
)
from edgy.core.terminal import Print
from edgy.exceptions import FieldDefinitionError
from edgy.protocols.many_relationship import ManyRelationProtocol

if TYPE_CHECKING:
    from edgy.core.db.models.types import BaseModelType


FK_CHAR_LIMIT = 63
terminal = Print()


class BaseForeignKeyField(BaseForeignKey):
    force_cascade_deletion_relation: bool = False
    relation_has_post_delete_callback: bool = False
    # overwrite for sondercharacters
    column_name: Optional[str] = None

    def __init__(
        self,
        *,
        on_update: str,
        on_delete: str,
        related_fields: Sequence[str] = (),
        no_constraint: bool = False,
        embed_parent: Optional[tuple[str, str]] = None,
        relation_fn: Optional[Callable[..., ManyRelationProtocol]] = None,
        reverse_path_fn: Optional[Callable[[str], tuple[Any, str, str]]] = None,
        remove_referenced: bool = False,
        null: bool = False,
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
        super().__init__(**kwargs, null=null)
        if self.on_delete == SET_DEFAULT and self.server_default is None:
            terminal.write_warning(
                "Declaring on_delete `SET DEFAULT` but providing no server_default."
            )
        if self.on_delete == SET_NULL and not self.null:
            terminal.write_warning("Declaring on_delete `SET NULL` but null is False.")

    async def _notset_post_delete_callback(self, value: Any, instance: "BaseModelType") -> None:
        value = self.expand_relationship(value)
        if value is not None:
            await value.delete(remove_referenced_call=True)

    async def pre_save_callback(
        self, value: Any, original_value: Any, force_insert: bool, instance: "BaseModelType"
    ) -> dict[str, Any]:
        target = self.target
        # value is clean result, check what is provided as kwarg
        # still use value for handling defaults
        if value is None or (isinstance(value, dict) and not value):
            value = original_value
        # e.g. default was a Model
        if isinstance(value, (target, target.proxy_model)):
            await value.save()
            return self.clean(self.name, value, for_query=False, hook_call=True)
        elif isinstance(value, dict):
            return await self.pre_save_callback(
                target(**value), original_value=None, force_insert=force_insert, instance=instance
            )
        # don't mess around when None, we cannot save something here
        if value is None:
            return {}
        return {self.name: value}

    def get_relation(self, **kwargs: Any) -> ManyRelationProtocol:
        if self.relation_fn is not None:
            return self.relation_fn(**kwargs)
        if self.force_cascade_deletion_relation:
            relation: Any = VirtualCascadeDeletionSingleRelation
        else:
            relation = SingleRelation
        return cast(
            ManyRelationProtocol,
            relation(
                to=self.owner, to_foreign_key=self.name, embed_parent=self.embed_parent, **kwargs
            ),
        )

    def traverse_field(self, path: str) -> tuple[Any, str, str]:
        return self.target, self.reverse_name, path.removeprefix(self.name).removeprefix("__")

    def reverse_traverse_field(self, path: str) -> tuple[Any, str, str]:
        if self.reverse_path_fn:
            return self.reverse_path_fn(path)
        return self.owner, self.name, path.removeprefix(self.reverse_name).removeprefix("__")

    @cached_property
    def related_columns(self) -> dict[str, Optional[sqlalchemy.Column]]:
        target = self.target
        columns: dict[str, Optional[sqlalchemy.Column]] = {}
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
                columns = dict.fromkeys(target.pkcolumns)
        return columns

    def expand_relationship(self, value: Any) -> Any:
        if value is None:
            return None
        target = self.target
        related_columns = self.related_columns.keys()
        if isinstance(value, (target, target.proxy_model)):
            # if all related columns are set to None
            if all(
                key in value.__dict__ and getattr(value, key) is None for key in related_columns
            ):
                return None
            return value
        if len(related_columns) == 1 and not isinstance(value, (dict, BaseModel)):
            value = {next(iter(related_columns)): value}
        elif isinstance(value, BaseModel):
            return self.expand_relationship({col: getattr(value, col) for col in related_columns})
        instance = target.proxy_model(**value)
        instance.identifying_db_fields = related_columns
        return instance

    def clean(
        self, name: str, value: Any, for_query: bool = False, hook_call: bool = False
    ) -> dict[str, Any]:
        retdict: dict[str, Any] = {}
        target = self.target
        phase = CURRENT_PHASE.get()
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
        elif isinstance(value, (target, target.proxy_model)):
            for column_name in column_names:
                translated_name = self.from_fk_field_name(name, column_name)
                if hasattr(value, translated_name):
                    retdict[column_name] = getattr(value, translated_name)
                elif phase in {"prepare_insert", "prepare_update"} and not hook_call:
                    # save model first when not fully specified
                    return {name: value}
        elif len(column_names) == 1:
            column_name = next(iter(column_names))
            retdict[column_name] = value
        else:
            raise ValueError(f"cannot handle: {value} of type {type(value)}")
        return retdict

    def reverse_clean(self, name: str, value: Any, for_query: bool = False) -> dict[str, Any]:
        if not for_query:
            return {}
        retdict: dict[str, Any] = {}
        column_names = self.owner.meta.field_to_column_names[self.name]
        assert len(column_names) >= 1
        if value is None:
            for column_name in column_names:
                retdict[self.from_fk_field_name(name, column_name)] = None
        elif isinstance(value, dict):
            for column_name in column_names:
                translated_name = self.from_fk_field_name(name, column_name)
                if translated_name in value:
                    retdict[translated_name] = value[translated_name]
        elif isinstance(value, BaseModel):
            for column_name in column_names:
                translated_name = self.from_fk_field_name(name, column_name)
                if hasattr(value, translated_name):
                    retdict[translated_name] = getattr(value, translated_name)
        elif len(column_names) == 1:
            translated_name = self.from_fk_field_name(name, next(iter(column_names)))
            retdict[translated_name] = value
        else:
            raise ValueError(f"cannot handle: {value} of type {type(value)}")
        return retdict

    def modify_input(self, name: str, kwargs: dict[str, Any]) -> None:
        phase = CURRENT_PHASE.get()
        column_names = self.get_column_names(name)
        assert len(column_names) >= 1
        if len(column_names) == 1:
            # fake default
            if phase in {"post_insert", "post_update", "load"}:
                kwargs.setdefault(name, None)
            return
        to_add = {}
        # for idempotency
        for column_name in column_names:
            if column_name in kwargs:
                to_add[self.from_fk_field_name(name, column_name)] = kwargs.pop(column_name)
        # empty
        if not to_add:
            # fake default
            if phase in {"post_insert", "post_update", "load"}:
                kwargs.setdefault(name, None)
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
        fk_name = f"{self.owner.meta.tablename}_{self.target.meta.tablename}_{name}"

        fk_name = f"fk_{fk_name}"
        return fk_name[:FK_CHAR_LIMIT]

    def get_fkindex_name(self, name: str) -> str:
        """
        Builds the fk name for the engine.

        Engines have a limitation of the foreign key being bigger than 63
        characters.

        if that happens, we need to assure it is small.
        """
        fk_name = f"{self.owner.meta.tablename}_{self.target.meta.tablename}_{name}"

        fk_name = f"fkindex_{fk_name}"
        return fk_name[:FK_CHAR_LIMIT]

    def get_fk_field_name(self, name: str, fieldname: str) -> str:
        if len(self.related_columns) == 1:
            return name
        return f"{name}_{fieldname}"

    def get_fk_column_name(self, name: str, fieldname: str) -> str:
        name = self.column_name or name
        if len(self.related_columns) == 1:
            return name
        return f"{name}_{fieldname}"

    def from_fk_field_name(self, name: str, fieldname: str) -> str:
        if len(self.related_columns) == 1:
            return next(iter(self.related_columns.keys()))
        return fieldname.removeprefix(f"{name}_")

    def get_columns(self, name: str) -> Sequence[sqlalchemy.Column]:
        target = self.target
        columns = []
        nullable = self.get_columns_nullable()
        for column_key, related_column in self.related_columns.items():
            if related_column is None:
                related_column = target.table.columns[column_key]
            fkcolumn_name = self.get_fk_field_name(name, column_key)
            # use the related column as reference
            fkcolumn = sqlalchemy.Column(
                key=fkcolumn_name,
                type_=related_column.type,
                name=self.get_fk_column_name(name, related_column.name),
                primary_key=self.primary_key,
                autoincrement=False,
                nullable=related_column.nullable or nullable,
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
    ) -> Sequence[Union[sqlalchemy.Constraint, sqlalchemy.Index]]:
        constraints: list[Union[sqlalchemy.Constraint, sqlalchemy.Index]] = []
        no_constraint = bool(
            no_constraint
            or self.no_constraint
            # this does not work because fks are checked in metadata
            # this implies is_cross_db and is just a stronger version
            or self.owner.meta.registry is not self.target.meta.registry
            or self.owner.database is not self.target.database
        )
        if not no_constraint:
            target = self.target
            assert not target.__is_proxy_model__
            # use the last prefix as fallback
            prefix = ""
            for schema in schemes:
                prefix = f"{schema}.{target.meta.tablename}" if schema else target.meta.tablename
                if prefix in target.meta.registry.metadata_by_url[str(target.database.url)].tables:
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
                sqlalchemy.Index(
                    self.get_fkindex_name(name),
                    *columns,
                    unique=self.unique,
                ),
            )

        return constraints


class ForeignKey(ForeignKeyFieldFactory):
    field_bases = (BaseForeignKeyField,)
    field_type: Any = Any

    def __new__(  # type: ignore
        cls,
        to: Union[type["BaseModelType"], str],
        **kwargs: Any,
    ) -> BaseFieldType:
        return super().__new__(cls, to=to, **kwargs)

    @classmethod
    def validate(cls, kwargs: dict[str, Any]) -> None:
        super().validate(kwargs)
        if kwargs.get("auto_compute_server_default"):
            raise FieldDefinitionError(
                '"auto_compute_server_default" is not supported for ForeignKey.'
            ) from None
        kwargs["auto_compute_server_default"] = False
        if kwargs.get("server_default"):
            raise FieldDefinitionError(
                '"server_default" is not supported for ForeignKey.'
            ) from None
        if kwargs.get("server_onupdate"):
            raise FieldDefinitionError(
                '"server_onupdate" is not supported for ForeignKey.'
            ) from None
        embed_parent = kwargs.get("embed_parent")
        if embed_parent and "__" in embed_parent[1]:
            raise FieldDefinitionError(
                '"embed_parent" second argument (for embedding parent) cannot contain "__".'
            )
