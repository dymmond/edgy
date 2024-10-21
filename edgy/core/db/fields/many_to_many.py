from collections.abc import Sequence
from functools import cached_property
from typing import TYPE_CHECKING, Any, Literal, Optional, Union, cast

from edgy.core.db.constants import CASCADE
from edgy.core.db.context_vars import CURRENT_INSTANCE
from edgy.core.db.fields.base import BaseForeignKey
from edgy.core.db.fields.exclude_field import ExcludeField
from edgy.core.db.fields.factories import ForeignKeyFieldFactory
from edgy.core.db.fields.foreign_keys import ForeignKey
from edgy.core.db.relationships.relation import ManyRelation
from edgy.core.utils.models import create_edgy_model
from edgy.exceptions import FieldDefinitionError
from edgy.protocols.many_relationship import ManyRelationProtocol

if TYPE_CHECKING:
    from edgy.core.db.fields.types import BaseFieldType
    from edgy.core.db.models.types import BaseModelType


class BaseManyToManyForeignKeyField(BaseForeignKey):
    is_m2m: bool = True

    def __init__(
        self,
        *,
        to_fields: Sequence[str] = (),
        to_foreign_key: str = "",
        from_fields: Sequence[str] = (),
        from_foreign_key: str = "",
        through: Union[str, type["BaseModelType"]] = "",
        through_tablename: str = "",
        embed_through: Union[str, Literal[False]] = "",
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.to_fields = to_fields
        self.to_foreign_key = to_foreign_key
        self.from_fields = from_fields
        self.from_foreign_key = from_foreign_key
        self.through = through
        self.through_tablename = through_tablename
        self.embed_through = embed_through

    @cached_property
    def embed_through_prefix(self) -> str:
        if self.embed_through is False:
            return ""
        if not self.embed_through:
            return self.name
        return f"{self.name}__{self.embed_through}"

    @cached_property
    def reverse_embed_through_prefix(self) -> str:
        if self.embed_through is False:
            return ""
        if not self.embed_through:
            return self.reverse_name
        return f"{self.reverse_name}__{self.embed_through}"

    def clean(self, name: str, value: Any, for_query: bool = False) -> dict[str, Any]:
        if not for_query:
            return {}
        raise NotImplementedError(f"Not implemented yet for ManyToMany {name}")

    def reverse_clean(self, name: str, value: Any, for_query: bool = False) -> dict[str, Any]:
        if not for_query:
            return {}
        raise NotImplementedError(f"Not implemented yet for ManyToMany {name}")

    def get_relation(self, **kwargs: Any) -> ManyRelationProtocol:
        assert not isinstance(self.through, str), "through not initialized yet"
        return ManyRelation(
            through=self.through,
            to=self.target,
            from_foreign_key=self.from_foreign_key,
            to_foreign_key=self.to_foreign_key,
            embed_through=self.embed_through,
            **kwargs,
        )

    def get_reverse_relation(self, **kwargs: Any) -> ManyRelationProtocol:
        assert not isinstance(self.through, str), "through not initialized yet"
        return ManyRelation(
            through=self.through,
            to=self.owner,
            reverse=True,
            from_foreign_key=self.to_foreign_key,
            to_foreign_key=self.from_foreign_key,
            embed_through=self.embed_through,
            **kwargs,
        )

    def traverse_field(self, path: str) -> tuple[Any, str, str]:
        if self.embed_through_prefix is False or self.embed_through_prefix:
            # select embedded
            if self.embed_through_prefix is not False and path.startswith(
                self.embed_through_prefix
            ):
                return (
                    self.through,
                    self.from_foreign_key,
                    path.removeprefix(self.embed_through_prefix).removeprefix("__"),
                )
            # proxy
            return (
                self.target,
                self.reverse_name,
                f'{path.removeprefix(self.name).removeprefix("__")}',
            )
        return self.target, self.reverse_name, path.removeprefix(self.name).removeprefix("__")

    def reverse_traverse_field_fk(self, path: str) -> tuple[Any, str, str]:
        # used for target fk
        if self.reverse_embed_through_prefix is False or path.startswith(
            self.reverse_embed_through_prefix
        ):
            # select embedded
            if self.reverse_embed_through_prefix and path.startswith(
                self.reverse_embed_through_prefix
            ):
                return (
                    self.through,
                    self.to_foreign_key,
                    path.removeprefix(self.reverse_embed_through_prefix).removeprefix("__"),
                )
            # proxy
            return (
                self.owner,
                self.name,
                f'{path.removeprefix(self.reverse_name).removeprefix("__")}',
            )
        return self.owner, self.name, path.removeprefix(self.reverse_name).removeprefix("__")

    def create_through_model(self) -> None:
        """
        Creates the default empty through model.

        Generates a middle model based on the owner of the field and the field itself and adds
        it to the main registry to make sure it generates the proper models and migrations.
        """
        from edgy.core.db.models.metaclasses import MetaInfo

        __bases__: tuple[type[BaseModelType], ...] = ()
        pknames = set()
        if self.through:
            if isinstance(self.through, str):
                assert self.owner.meta.registry, "no registry found"
                self.through = self.owner.meta.registry.models[self.through]
            through = self.through
            if through.meta.abstract:
                pknames = set(through.pknames)
                __bases__ = (through,)
            else:
                if not self.from_foreign_key:
                    candidate = None
                    for field_name in through.meta.foreign_key_fields:
                        field = through.meta.fields[field_name]
                        if field.target == self.owner:
                            if candidate:
                                raise ValueError("multiple foreign keys to owner")
                            else:
                                candidate = field_name
                    if not candidate:
                        raise ValueError("no foreign key fo owner found")
                    self.from_foreign_key = candidate
                if not self.to_foreign_key:
                    candidate = None
                    for field_name in through.meta.foreign_key_fields:
                        field = through.meta.fields[field_name]
                        if field.target == self.target:
                            if candidate:
                                raise ValueError("multiple foreign keys to target")
                            else:
                                candidate = field_name
                    if not candidate:
                        raise ValueError("no foreign key fo target found")
                    self.to_foreign_key = candidate
                through.meta.multi_related.add((self.from_foreign_key, self.to_foreign_key))
                return
        assert self.owner.meta.registry, "no registry set"
        owner_name = self.owner.__name__
        to_name = self.target.__name__
        class_name = f"{owner_name}{to_name}"
        if not self.from_foreign_key:
            self.from_foreign_key = owner_name.lower()

        if not self.to_foreign_key:
            self.to_foreign_key = to_name.lower()

        tablename = self.through_tablename or f"{self.from_foreign_key}s_{self.to_foreign_key}s"
        meta_args = {
            "tablename": tablename,
            "multi_related": {(self.from_foreign_key, self.to_foreign_key)},
        }
        has_pknames = pknames and not pknames.issubset(
            {self.from_foreign_key, self.to_foreign_key}
        )
        if has_pknames:
            meta_args["unique_together"] = [(self.from_foreign_key, self.to_foreign_key)]

        new_meta: MetaInfo = MetaInfo(None, **meta_args)

        to_related_name: Union[str, Literal[False]]
        if self.related_name is False:
            to_related_name = False
        elif self.related_name:
            to_related_name = f"{self.related_name}"
            self.reverse_name = to_related_name
        else:
            if self.unique:
                to_related_name = f"{to_name.lower()}_{class_name.lower()}"
            else:
                to_related_name = f"{to_name.lower()}_{class_name.lower()}s_set"
            self.reverse_name = to_related_name

        # in any way m2m fields will have an index (either by unique_together or by their primary key constraint)

        fields = {
            f"{self.from_foreign_key}": ForeignKey(
                self.owner,
                on_delete=CASCADE,
                related_name=False,
                reverse_name=self.name,
                related_fields=self.from_fields,
                primary_key=not has_pknames,
                index=self.index,
            ),
            f"{self.to_foreign_key}": ForeignKey(
                self.target,
                on_delete=CASCADE,
                unique=self.unique,
                related_name=to_related_name,
                related_fields=self.to_fields,
                embed_parent=(self.from_foreign_key, self.embed_through or ""),
                primary_key=not has_pknames,
                index=self.index,
                relation_fn=self.get_reverse_relation,
                reverse_path_fn=self.reverse_traverse_field_fk,
            ),
        }

        # Create the through model, which adds itself to registry
        through_model = create_edgy_model(
            __name__=class_name,
            __module__=self.__module__,
            __definitions__=fields,
            __metadata__=new_meta,
            __bases__=__bases__,
        )
        if "content_type" not in through_model.meta.fields:
            through_model.meta.fields["content_type"] = ExcludeField(
                name="content_type", owner=through_model
            )
        through_model.add_to_registry(self.owner.meta.registry)
        self.through = through_model

    def to_model(
        self,
        field_name: str,
        value: Any,
    ) -> dict[str, Any]:
        """
        Meta field
        """
        instance = cast("BaseModelType", CURRENT_INSTANCE.get())
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

    def has_default(self) -> bool:
        """Checks if the field has a default value set"""
        return False

    def get_default_values(self, field_name: str, cleaned_data: dict[str, Any]) -> Any:
        """
        Meta field
        """
        return {}

    def __get__(self, instance: "BaseModelType", owner: Any = None) -> ManyRelationProtocol:
        if instance:
            if instance.__dict__.get(self.name, None) is None:
                instance.__dict__[self.name] = self.get_relation()
            if instance.__dict__[self.name].instance is None:
                instance.__dict__[self.name].instance = instance
            return instance.__dict__[self.name]  # type: ignore
        raise ValueError("Missing instance")

    async def post_save_callback(
        self, value: ManyRelationProtocol, instance: "BaseModelType", force_insert: bool
    ) -> None:
        await value.save_related()


class ManyToManyField(ForeignKeyFieldFactory):
    field_type: Any = Any
    field_bases = (BaseManyToManyForeignKeyField,)

    def __new__(  # type: ignore
        cls,
        to: Union["BaseModelType", str],
        *,
        through: Optional["BaseModelType"] = None,
        from_fields: Sequence[str] = (),
        to_fields: Sequence[str] = (),
        **kwargs: Any,
    ) -> "BaseFieldType":
        return super().__new__(
            cls, to=to, through=through, from_fields=from_fields, to_fields=to_fields, **kwargs
        )

    @classmethod
    def validate(cls, kwargs: dict[str, Any]) -> None:
        super().validate(kwargs)
        embed_through = kwargs.get("embed_through")
        if embed_through and "__" in embed_through:
            raise FieldDefinitionError('"embed_through" cannot contain "__".')

        kwargs["null"] = True
        kwargs["on_delete"] = CASCADE
        kwargs["on_update"] = CASCADE


ManyToMany = ManyToManyField
