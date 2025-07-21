from __future__ import annotations

import contextlib
from collections.abc import Sequence
from functools import cached_property
from typing import TYPE_CHECKING, Any, Literal, cast

from pydantic import SkipValidation

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
    from edgy import Model
    from edgy.core.connection.registry import Registry
    from edgy.core.db.fields.types import BaseFieldType
    from edgy.core.db.models.types import BaseModelType

# Character limit for generated many-to-many table names.
M2M_TABLE_NAME_LIMIT = 64
# Keywords to exclude from kwargs when initializing a ManyToManyField.
CLASS_DEFAULTS = ["cls", "__class__", "kwargs"]


class BaseManyToManyForeignKeyField(BaseForeignKey):
    """
    Base class for defining Many-to-Many foreign key relationships in Edgy models.

    This class extends `BaseForeignKey` to handle the complexities of M2M relationships,
    which involve an intermediate "through" table. It manages the creation and
    interaction with this through table, including foreign keys to the owner and
    target models.

    Attributes:
        is_m2m (bool): Always `True` for Many-to-Many fields.
        to_fields (Sequence[str]): Fields on the `target` model that the `through`
                                  model's foreign key to `target` will reference.
        to_foreign_key (str): The name of the foreign key field in the `through`
                             model that points to the `target` model.
        from_fields (Sequence[str]): Fields on the `owner` model that the `through`
                                    model's foreign key to `owner` will reference.
        from_foreign_key (str): The name of the foreign key field in the `through`
                               model that points to the `owner` model.
        through (str | type["BaseModelType"]): The intermediate model that defines
                                              the many-to-many relationship. Can be
                                              a model class or its string name.
        through_tablename (str | type[OLD_M2M_NAMING] | type[NEW_M2M_NAMING]):
            The name of the database table for the `through` model, or a constant
            indicating a naming convention (`OLD_M2M_NAMING` or `NEW_M2M_NAMING`).
        embed_through (str | Literal[False]): If a string, it indicates the attribute
                                              name to embed the `through` model directly
                                              into queries. If `False`, no embedding.
    """

    is_m2m: bool = True

    def __init__(
        self,
        *,
        to_fields: Sequence[str] = (),
        to_foreign_key: str = "",
        from_fields: Sequence[str] = (),
        from_foreign_key: str = "",
        through: str | type[BaseModelType] = "",
        through_tablename: str | type[OLD_M2M_NAMING] | type[NEW_M2M_NAMING],
        embed_through: str | Literal[False] = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        # Skip Pydantic validation as Edgy handles extended logic for M2M fields.
        self.metadata.append(SkipValidation())
        self.to_fields = to_fields
        self.to_foreign_key = to_foreign_key
        self.from_fields = from_fields
        self.from_foreign_key = from_foreign_key
        # Store original and current 'through' value, as it can be a string resolved later.
        self.through_original = self.through = through
        self.through_tablename = through_tablename
        self.embed_through = embed_through

    @cached_property
    def embed_through_prefix(self) -> str:
        """
        Generates the prefix used for embedding the 'through' model in queries.

        This prefix is constructed using the field's `name` and the `embed_through`
        attribute, allowing nested query paths like `my_m2m_field__through_attr`.
        """
        if self.embed_through is False:
            return ""
        if not self.embed_through:
            return self.name
        return f"{self.name}__{self.embed_through}"

    @cached_property
    def reverse_embed_through_prefix(self) -> str:
        """
        Generates the prefix used for embedding the 'through' model in reverse queries.

        Similar to `embed_through_prefix`, but for the reverse relationship, using
        the `reverse_name` of the field.
        """
        if self.embed_through is False:
            return ""
        if not self.embed_through:
            return self.reverse_name
        return f"{self.reverse_name}__{self.embed_through}"

    @property
    def through_registry(self) -> Registry:
        """
        Returns the registry associated with the 'through' model.

        If `through` is a string, this registry is used to resolve the model.
        It defaults to the owner model's registry if not explicitly set.
        """
        if not hasattr(self, "_through_registry"):
            assert self.owner.meta.registry, "no registry found neither 'through_registry' set"
            return self.owner.meta.registry
        return cast("Registry", self._through_registry)

    @through_registry.setter
    def through_registry(self, value: Any) -> None:
        """Sets the registry for the 'through' model."""
        self._through_registry = value

    @through_registry.deleter
    def through_registry(self) -> None:
        """Deletes the 'through' registry attribute."""
        with contextlib.suppress(AttributeError):
            delattr(self, "_through_registry")

    def clean(self, name: str, value: Any, for_query: bool = False) -> dict[str, Any]:
        """
        Cleans the input value for a Many-to-Many field.

        Currently, this method is primarily intended for query generation.
        """
        if not for_query:
            return {}
        raise NotImplementedError(f"Not implemented yet for ManyToMany {name}")

    def reverse_clean(self, name: str, value: Any, for_query: bool = False) -> dict[str, Any]:
        """
        Cleans the input value for a reverse Many-to-Many field.

        Currently, this method is primarily intended for query generation.
        """
        if not for_query:
            return {}
        raise NotImplementedError(f"Not implemented yet for ManyToMany {name}")

    def get_relation(self, **kwargs: Any) -> ManyRelationProtocol:
        """
        Returns the `ManyRelation` object for this Many-to-Many field.

        This object handles the operations on the through table.
        """
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
        """
        Returns the `ManyRelation` object for the reverse of this Many-to-Many field.

        This allows traversing the relationship from the target model back to the owner.
        """
        assert not isinstance(self.through, str), "through not initialized yet"
        return ManyRelation(
            through=self.through,
            to=self.owner,
            reverse=True,  # Indicate that this is a reverse relation.
            from_foreign_key=self.to_foreign_key,  # Flipped for reverse.
            to_foreign_key=self.from_foreign_key,  # Flipped for reverse.
            embed_through=self.embed_through,
            **kwargs,
        )

    def traverse_field(self, path: str) -> tuple[Any, str, str]:
        """
        Traverses the field path for a Many-to-Many relationship.

        This method determines whether the path refers to the embedded `through`
        model or the `target` model, and returns the appropriate model,
        relation name, and remaining path.
        """
        # Check if embedding is disabled or an embedded prefix is set.
        # empty string (new way and no embedding) is to use always owner
        if self.embed_through_prefix and path.startswith(self.embed_through_prefix):
            return (
                self.through,  # The intermediate model.
                self.from_foreign_key,  # The foreign key from 'through' to 'owner'.
                path.removeprefix(self.embed_through_prefix).removeprefix("__"),  # Remaining path.
            )
        # Otherwise, assume it's traversing to the target model (the "proxy" relation).
        return (
            self.target,  # The model being traversed to.
            self.reverse_name,  # The reverse name on the target.
            f"{path.removeprefix(self.name).removeprefix('__')}",  # Remaining path.
        )

    def reverse_traverse_field_fk(self, path: str) -> tuple[Any, str, str]:
        """
        Traverses the field path in reverse for a Many-to-Many foreign key.

        This is used when a relationship is being queried from the `target` model
        back towards the `owner` via the `through` model.
        """
        # used for target foreign_key
        # Check if embedding is enabled and the path starts with the reverse embedded prefix.
        # empty string (new way and no embedding) is to use always owner
        if self.reverse_embed_through_prefix and path.startswith(
            self.reverse_embed_through_prefix
        ):
            # If embedding the through model, return the through model itself.
            return (
                self.through,  # The model being traversed to.
                self.to_foreign_key,  # The foreign key from 'through' to 'target'.
                path.removeprefix(self.reverse_embed_through_prefix).removeprefix("__"),
            )
        # Otherwise, assume it's traversing to the owner model (the "proxy" relation).
        return (
            self.owner,  # The model being traversed to.
            self.name,  # The name of this M2M field.
            f"{path.removeprefix(self.reverse_name).removeprefix('__')}",
        )

    def create_through_model(
        self,
        *,
        replace_related_field: bool
        | type[BaseModelType]
        | tuple[type[BaseModelType], ...]
        | list[type[BaseModelType]] = False,
    ) -> None:
        """
        Creates or configures the intermediate "through" model for the Many-to-Many relationship.

        If a `through` model is explicitly provided (as a class or string name),
        this method configures it. If no `through` model is provided, it dynamically
        generates a default intermediate model with foreign keys to the `owner` and `target` models.
        It also handles multi-tenancy implications and ensures proper registration.
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
        in_admin_default = False
        no_admin_create_default = True
        pknames = set()  # Primary key names for the 'through' model.

        if self.through:
            through = self.through
            if isinstance(through, str):
                # If 'through' is a string, register a callback to resolve it later.
                def callback(model_class: type[BaseModelType]) -> None:
                    self.through = model_class
                    self.create_through_model(replace_related_field=replace_related_field)

                self.through_registry.register_callback(through, callback, one_time=True)
                return

            # If 'through' is a model class.
            if not through.meta.abstract:
                # If the through model is not abstract, ensure it's in the registry.
                if not through.meta.registry:
                    through = cast(
                        "type[BaseModelType]",
                        through.add_to_registry(
                            self.through_registry,
                            replace_related_field=replace_related_field,
                            on_conflict="keep",
                        ),
                    )
                # Auto-detect `from_foreign_key` if not provided.
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
                # Auto-detect `to_foreign_key` if not provided.
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
                # Add the foreign key pair to the through model's multi_related.
                through.meta.multi_related.add((self.from_foreign_key, self.to_foreign_key))
                self.through = through
                return
            # If `through` is an abstract model, inherit its `pknames` and admin settings.
            pknames = set(through.pknames)
            __bases__ = (through,)
            if through.meta.in_admin is not None:
                in_admin_default = through.meta.in_admin
            if through.meta.no_admin_create is not None:
                no_admin_create_default = through.meta.no_admin_create
            del through  # Clean up reference to the abstract model.

        assert self.owner.meta.registry, "no registry set"
        owner_name = self.owner.__name__
        target_name = self.target.__name__

        class_name = f"{owner_name}{self.name.capitalize()}Through"

        # Set default foreign key names if not provided.
        if not self.from_foreign_key:
            self.from_foreign_key = owner_name.lower()

        if not self.to_foreign_key:
            self.to_foreign_key = target_name.lower()

        # Determine the through table name based on conventions or explicit name.
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
        # If the abstract through model had primary keys not part of the FKs, add unique_together.
        has_pknames = pknames and not pknames.issubset(
            {self.from_foreign_key, self.to_foreign_key}
        )
        if has_pknames:
            meta_args["unique_together"] = [(self.from_foreign_key, self.to_foreign_key)]

        # Create MetaInfo for the dynamically generated through model.
        # TenantMeta is used if either owner or target is a TenantModel.
        new_meta: MetaInfo = TenantMeta(
            None,
            registry=False,  # Will be added to registry explicitly later.
            no_copy=True,
            is_tenant=getattr(self.owner.meta, "is_tenant", False)
            or getattr(self.target.meta, "is_tenant", False),
            register_default=getattr(self.owner.meta, "register_default", None),
            in_admin=in_admin_default,
            no_admin_create=no_admin_create_default,
            **meta_args,
        )

        to_related_name: str | Literal[False]
        # Determine the `related_name` for the foreign key pointing to the target.
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

        # Define the fields for the dynamically created through model.
        # These are essentially two ForeignKey fields pointing to the owner and target.
        fields = {
            f"{self.from_foreign_key}": ForeignKey(
                self.owner,
                on_delete=CASCADE,
                related_name=False,  # No reverse relation on the owner side for this FK.
                reverse_name=self.name,  # The name of the M2M field on the owner.
                related_fields=self.from_fields,
                primary_key=not has_pknames,  # PK if no custom PKs were inherited.
                index=self.index,
            ),
            f"{self.to_foreign_key}": ForeignKey(
                self.target,
                on_delete=CASCADE,
                unique=self.unique,
                related_name=to_related_name,
                related_fields=self.to_fields,
                embed_parent=(
                    self.from_foreign_key,
                    self.embed_through or "",
                ),  # How to embed the owner.
                primary_key=not has_pknames,
                index=self.index,
                relation_fn=self.get_reverse_relation,  # Custom relation for reverse traversal.
                reverse_path_fn=self.reverse_traverse_field_fk,  # Custom reverse path for FK.
            ),
        }

        # Create the 'through' model using `create_edgy_model`.
        through_model = create_edgy_model(
            __name__=class_name,
            __module__=self.__module__,
            __definitions__=fields,
            __metadata__=new_meta,
            __bases__=__bases__,
        )
        # Add a placeholder for 'content_type' if it's not present, often used in generic relations.
        if "content_type" not in through_model.meta.fields:
            through_model.meta.fields["content_type"] = ExcludeField(
                name="content_type", owner=through_model
            )
        # Add the newly created through model to the registry.
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
        Converts the input value for a Many-to-Many field into a `ManyRelationProtocol` object.

        This method is called during model initialization to set up the M2M relation
        for an instance. If an instance is available, it stages the given values for
        later saving. Otherwise, it creates a relation with references.
        """
        instance = cast("BaseModelType", CURRENT_INSTANCE.get())
        if isinstance(value, ManyRelationProtocol):
            return {field_name: value}
        if instance:
            # If an instance exists, get the relation object and stage the new values.
            relation_instance = self.__get__(instance)
            if not isinstance(value, Sequence):
                value = [value]
            relation_instance.stage(*value)
        else:
            # If no instance, create a relation with immediate references.
            relation_instance = self.get_relation(refs=value)
        return {field_name: relation_instance}

    def has_default(self) -> bool:
        """
        Checks if the field has a default value set.

        Many-to-Many fields do not typically have simple default values in the database.
        """
        return False

    def get_default_values(self, field_name: str, cleaned_data: dict[str, Any]) -> Any:
        """
        Retrieves default values for the field.

        For Many-to-Many fields, this method returns an empty dictionary as defaults
        are managed via relation staging.
        """
        return {}

    def __get__(self, instance: BaseModelType, owner: Any = None) -> ManyRelationProtocol:
        """
        Descriptor method for accessing the Many-to-Many relationship on a model instance.

        When `model_instance.m2m_field` is accessed, this method returns the
        `ManyRelationProtocol` object associated with that instance, initializing it
        if it hasn't been already.
        """
        if instance:
            # If the relation hasn't been set or is None, initialize it.
            if instance.__dict__.get(self.name, None) is None:
                instance.__dict__[self.name] = self.get_relation()
            # Ensure the relation object has a reference to its instance.
            if instance.__dict__[self.name].instance is None:
                instance.__dict__[self.name].instance = instance
            return instance.__dict__[self.name]  # type: ignore
        raise ValueError("Missing instance")

    async def post_save_callback(self, value: ManyRelationProtocol, is_update: bool) -> None:
        """
        Callback executed after a model instance is saved.

        This method ensures that any staged Many-to-Many relationships are
        persisted to the database via the `save_related` method of the relation object.
        """
        await value.save_related()


class ManyToManyField(ForeignKeyFieldFactory, list):
    """
    A factory for creating `ManyToManyField` instances in Edgy models.

    This factory ensures proper validation and default settings for Many-to-Many
    fields, including the `through_tablename` and disallowing server-side defaults.
    """

    field_type: Any = Any
    field_bases: tuple = (BaseManyToManyForeignKeyField,)

    def __new__(
        cls,
        to: BaseModelType | type[Model] | str,
        *,
        to_fields: Sequence[str] = (),
        to_foreign_key: str = "",
        from_fields: Sequence[str] = (),
        from_foreign_key: str = "",
        through: str | type[BaseModelType] | type[Model] = "",
        through_tablename: str | type[OLD_M2M_NAMING] | type[NEW_M2M_NAMING] = "",
        embed_through: str | Literal[False] = False,
        **kwargs: Any,
    ) -> BaseFieldType:
        """
        Creates a new `ManyToManyField` instance.

        Args:
            to (Union[BaseModelType, type[Model], str]): The target model class or its string name.
            to_fields (Sequence[str]): Fields on the `target` model that the `through`
                                      model's foreign key to `target` will reference.
            to_foreign_key (str): The name of the foreign key field in the `through`
                                 model that points to the `target` model.
            from_fields (Sequence[str]): Fields on the `owner` model that the `through`
                                        model's foreign key to `owner` will reference.
            from_foreign_key (str): The name of the foreign key field in the `through`
                                   model that points to the `owner` model.
            through (str | type[BaseModelType] | type[Model]): The intermediate model.
            through_tablename (str | type[OLD_M2M_NAMING] | type[NEW_M2M_NAMING]):
                The name of the database table for the `through` model.
            embed_through (str | Literal[False]): If a string, embeds the `through` model.
            **kwargs (Any): Additional keyword arguments.

        Returns:
            BaseFieldType: The constructed `ManyToManyField` instance.
        """
        # Collect all relevant arguments into kwargs, excluding class-specific ones.
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
        """
        Validates the parameters for a `ManyToManyField` field.

        Enforces rules specific to Many-to-Many fields, such as disallowing
        server-side defaults/updates and ensuring `through_tablename` is set
        correctly. It also sets default values for `null`, `exclude`, `on_delete`,
        and `on_update`.

        Args:
            kwargs (dict[str, Any]): The dictionary of keyword arguments passed
                                     during field construction.

        Raises:
            FieldDefinitionError: If any validation rule is violated.
        """
        super().validate(kwargs)
        # Disallow auto_compute_server_default.
        if kwargs.get("auto_compute_server_default"):
            raise FieldDefinitionError(
                '"auto_compute_server_default" is not supported for ManyToMany.'
            ) from None
        kwargs["auto_compute_server_default"] = False
        # Disallow server_default.
        if kwargs.get("server_default"):
            raise FieldDefinitionError(
                '"server_default" is not supported for ManyToMany.'
            ) from None
        # Disallow server_onupdate.
        if kwargs.get("server_onupdate"):
            raise FieldDefinitionError(
                '"server_onupdate" is not supported for ManyToMany.'
            ) from None
        # Validate embed_through format.
        embed_through = kwargs.get("embed_through")
        if embed_through and "__" in embed_through:
            raise FieldDefinitionError('"embed_through" cannot contain "__".')

        # Set default values specific to Many-to-Many fields.
        kwargs["null"] = True  # M2M fields are conceptually null until related.
        kwargs["exclude"] = True  # M2M fields are typically excluded from direct model data.
        kwargs["on_delete"] = CASCADE  # Default cascade for M2M through table FKs.
        kwargs["on_update"] = CASCADE  # Default cascade for M2M through table FKs.

        # Validate through_tablename.
        through_tablename: str | type[OLD_M2M_NAMING] | type[NEW_M2M_NAMING] = kwargs.get(
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


# Alias ManyToManyField for convenience.
ManyToMany = ManyToManyField
