import contextlib
from collections.abc import Sequence
from functools import cached_property
from typing import TYPE_CHECKING, Any, Literal, Union, cast

from edgy.core.db.constants import CASCADE, NEW_M2M_NAMING, OLD_M2M_NAMING
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
    from edgy.core.connection.registry import Registry
    from edgy.core.db.fields.types import BaseFieldType
    from edgy.core.db.models.types import BaseModelType

M2M_TABLE_NAME_LIMIT = 64
CLASS_DEFAULTS = ["cls", "__class__", "kwargs"]


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
        through_tablename: Union[str, type[OLD_M2M_NAMING], type[NEW_M2M_NAMING]],
        embed_through: Union[str, Literal[False]] = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.to_fields = to_fields
        self.to_foreign_key = to_foreign_key
        self.from_fields = from_fields
        self.from_foreign_key = from_foreign_key
        self.through_original = self.through = through
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

    @property
    def through_registry(self) -> "Registry":
        """Registry searched in case through is a string"""

        if not hasattr(self, "_through_registry"):
            assert self.owner.meta.registry, "no registry found neither 'through_registry' set"
            return self.owner.meta.registry
        return cast("Registry", self._through_registry)

    @through_registry.setter
    def through_registry(self, value: Any) -> None:
        self._through_registry = value

    @through_registry.deleter
    def through_registry(self) -> None:
        with contextlib.suppress(AttributeError):
            delattr(self, "_through_registry")

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
                f"{path.removeprefix(self.name).removeprefix('__')}",
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
                f"{path.removeprefix(self.reverse_name).removeprefix('__')}",
            )
        return self.owner, self.name, path.removeprefix(self.reverse_name).removeprefix("__")

    def create_through_model(
        self,
        *,
        replace_related_field: Union[
            bool,
            type["BaseModelType"],
            tuple[type["BaseModelType"], ...],
            list[type["BaseModelType"]],
        ] = False,
    ) -> None:
        """
        Creates the default empty through model.

        Generates a middle model based on the owner of the field and the field itself and adds
        it to the main registry to make sure it generates the proper models and migrations.
        """
        from edgy.contrib.multi_tenancy.base import TenantModel
        from edgy.contrib.multi_tenancy.metaclasses import TenantMeta
        from edgy.core.db.models.metaclasses import MetaInfo

        __bases__: tuple[type[BaseModelType], ...] = (
            (TenantModel,)
            if getattr(self.owner.meta, "is_tenant", False)
            or getattr(self.target.meta, "is_tenant", False)
            else ()
        )
        pknames = set()
        if self.through:
            through = self.through
            if isinstance(through, str):

                def callback(model_class: type["BaseModelType"]) -> None:
                    self.through = model_class
                    self.create_through_model(replace_related_field=replace_related_field)

                self.through_registry.register_callback(through, callback, one_time=True)
                return
            if not through.meta.abstract:
                if not through.meta.registry:
                    through = cast(
                        "type[BaseModelType]",
                        through.add_to_registry(
                            self.through_registry,
                            replace_related_field=replace_related_field,
                            on_conflict="keep",
                        ),
                    )
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
                        raise ValueError("no foreign key to owner found")
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
                        raise ValueError("no foreign key to target found")
                    self.to_foreign_key = candidate
                through.meta.multi_related.add((self.from_foreign_key, self.to_foreign_key))
                self.through = through
                return
            pknames = set(through.pknames)
            __bases__ = (through,)
            del through
        assert self.owner.meta.registry, "no registry set"
        owner_name = self.owner.__name__
        target_name = self.target.__name__

        class_name = f"{owner_name}{self.name.capitalize()}Through"

        if not self.from_foreign_key:
            self.from_foreign_key = owner_name.lower()

        if not self.to_foreign_key:
            self.to_foreign_key = target_name.lower()

        if self.through_tablename is OLD_M2M_NAMING:
            tablename: str = f"{self.from_foreign_key}s_{self.to_foreign_key}s"
        elif self.through_tablename is NEW_M2M_NAMING:
            tablename = class_name.lower()[:M2M_TABLE_NAME_LIMIT]
        else:
            tablename = (
                cast(str, self.through_tablename).format(field=self)[:M2M_TABLE_NAME_LIMIT].lower()
            )

        meta_args = {
            "tablename": tablename,
            "multi_related": {(self.from_foreign_key, self.to_foreign_key)},
        }
        has_pknames = pknames and not pknames.issubset(
            {self.from_foreign_key, self.to_foreign_key}
        )
        if has_pknames:
            meta_args["unique_together"] = [(self.from_foreign_key, self.to_foreign_key)]

        # TenantMeta is compatible to normal meta
        new_meta: MetaInfo = TenantMeta(
            None,
            registry=False,
            no_copy=True,
            is_tenant=getattr(self.owner.meta, "is_tenant", False)
            or getattr(self.target.meta, "is_tenant", False),
            register_default=getattr(self.owner.meta, "register_default", False),
            **meta_args,
        )

        to_related_name: Union[str, Literal[False]]
        if self.related_name is False:
            to_related_name = False
        elif self.related_name:
            to_related_name = f"{self.related_name}"
            self.reverse_name = to_related_name
        else:
            related_class_name = f"{owner_name}{target_name}"
            if self.unique:
                to_related_name = f"{target_name}_{related_class_name}".lower()
            else:
                to_related_name = f"{target_name}_{related_class_name}s_set".lower()
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
        self.through = through_model.add_to_registry(
            self.through_registry,
            replace_related_field=replace_related_field,
            on_conflict="keep",
        )

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
        to_fields: Sequence[str] = (),
        to_foreign_key: str = "",
        from_fields: Sequence[str] = (),
        from_foreign_key: str = "",
        through: Union[str, type["BaseModelType"]] = "",
        through_tablename: Union[str, type[OLD_M2M_NAMING], type[NEW_M2M_NAMING]] = "",
        embed_through: Union[str, Literal[False]] = False,
        **kwargs: Any,
    ) -> "BaseFieldType":
        kwargs = {
            **kwargs,
            **{key: value for key, value in locals().items() if key not in CLASS_DEFAULTS},
        }
        return super().__new__(
            cls,
            **kwargs,
        )

    @classmethod
    def validate(cls, kwargs: dict[str, Any]) -> None:
        super().validate(kwargs)
        if kwargs.get("auto_compute_server_default"):
            raise FieldDefinitionError(
                '"auto_compute_server_default" is not supported for ManyToMany.'
            ) from None
        kwargs["auto_compute_server_default"] = False
        if kwargs.get("server_default"):
            raise FieldDefinitionError(
                '"server_default" is not supported for ManyToMany.'
            ) from None
        if kwargs.get("server_onupdate"):
            raise FieldDefinitionError(
                '"server_onupdate" is not supported for ManyToMany.'
            ) from None
        embed_through = kwargs.get("embed_through")
        if embed_through and "__" in embed_through:
            raise FieldDefinitionError('"embed_through" cannot contain "__".')

        kwargs["null"] = True
        kwargs["exclude"] = True
        kwargs["on_delete"] = CASCADE
        kwargs["on_update"] = CASCADE
        through_tablename: Union[str, type[OLD_M2M_NAMING], type[NEW_M2M_NAMING]] = kwargs.get(
            "through_tablename"
        )
        if not through_tablename or (
            not isinstance(through_tablename, str)
            and through_tablename is not OLD_M2M_NAMING
            and through_tablename is not NEW_M2M_NAMING
        ):
            raise FieldDefinitionError(
                '"through_tablename" must be set to either OLD_M2M_NAMING, NEW_M2M_NAMING or a non-empty string.'
            )


ManyToMany = ManyToManyField
