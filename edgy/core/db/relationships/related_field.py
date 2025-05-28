from __future__ import annotations

import functools
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, cast

from pydantic import SkipValidation
from pydantic.json_schema import SkipJsonSchema

from edgy.core.db.context_vars import CURRENT_MODEL_INSTANCE
from edgy.core.db.fields.base import RelationshipField
from edgy.core.db.fields.foreign_keys import BaseForeignKeyField
from edgy.protocols.many_relationship import ManyRelationProtocol

if TYPE_CHECKING:
    from edgy.core.connection.database import Database
    from edgy.core.db.models.types import BaseModelType


class RelatedField(RelationshipField):
    """
    When a `related_name` is generated, creates a RelatedField from the table pointed
    from the ForeignKey declaration and the the table declaring it.
    """

    def __init__(
        self,
        *,
        foreign_key_name: str,
        related_from: type[BaseModelType],
        **kwargs: Any,
    ) -> None:
        self.foreign_key_name = foreign_key_name
        self.related_from = related_from
        super().__init__(
            inherit=False,
            exclude=True,
            field_type=list[related_from],  # type: ignore
            annotation=list[related_from],  # type: ignore
            column_type=None,
            null=True,
            no_copy=True,
            **kwargs,
        )
        # use edgy validation instead, we have an extended logic
        self.metadata.append(SkipValidation())
        # skip for now, we don't know if it is a m2m through model
        self.metadata.append(SkipJsonSchema())
        if self.foreign_key.relation_has_post_delete_callback:
            self.post_delete_callback = self._notset_post_delete_callback

    @property
    def related_to(self) -> type[BaseModelType]:
        return self.owner

    @property
    def related_name(self) -> str:
        return self.name

    def to_model(
        self,
        field_name: str,
        value: Any,
    ) -> dict[str, Any]:
        """
        Meta field
        """
        instance = CURRENT_MODEL_INSTANCE.get()
        if isinstance(value, ManyRelationProtocol):
            return {field_name: value}
        if instance:
            relation_instance = self.__get__(instance)
            if not isinstance(value, Sequence):
                value = [value]
            relation_instance.stage(*value)
        else:
            relation_instance = self.get_relation(refs=value)
        return {field_name: relation_instance}

    def __get__(self, instance: BaseModelType, owner: Any = None) -> ManyRelationProtocol:
        if not instance:
            raise ValueError("missing instance")

        if instance.__dict__.get(self.name, None) is None:
            instance.__dict__[self.name] = self.get_relation()
        if instance.__dict__[self.name].instance is None:
            instance.__dict__[self.name].instance = instance
        return instance.__dict__[self.name]  # type: ignore

    @functools.cached_property
    def foreign_key(self) -> BaseForeignKeyField:
        return cast(BaseForeignKeyField, self.related_from.meta.fields[self.foreign_key_name])

    def traverse_field(self, path: str) -> tuple[Any, str, str]:
        return self.foreign_key.reverse_traverse_field(path)

    def get_relation(self, **kwargs: Any) -> ManyRelationProtocol:
        return self.foreign_key.get_relation(**kwargs)

    def is_cross_db(self, owner_database: Database | None = None) -> bool:
        if owner_database is None:
            owner_database = self.owner.database
        return str(owner_database.url) != str(self.foreign_key.owner.database.url)

    def get_related_model_for_admin(self) -> type[BaseModelType] | None:
        related_from_registry = self.related_from.meta.registry
        assert related_from_registry is not None and related_from_registry is not False
        if self.related_from.__name__ in related_from_registry.admin_models:
            # FIXME: handle embedded
            return self.related_from
        return None

    @property
    def is_m2m(self) -> bool:
        return self.foreign_key.is_m2m

    def clean(self, name: str, value: Any, for_query: bool = False) -> dict[str, Any]:
        return self.foreign_key.reverse_clean(name, value, for_query=for_query)

    def __repr__(self) -> str:
        return f"<{type(self).__name__}: {self}>"

    def __str__(self) -> str:
        return f"({self.related_to.__name__}={self.related_name})"

    async def post_save_callback(self, value: ManyRelationProtocol, is_update: bool) -> None:
        await value.save_related()

    async def _notset_post_delete_callback(self, value: ManyRelationProtocol) -> None:
        if hasattr(value, "post_delete_callback"):
            await value.post_delete_callback()
