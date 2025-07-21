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
    Represents a reverse relationship field, typically generated for a `related_name`
    in a ForeignKey declaration. This field allows access to related instances
    from the "one" side of a one-to-many relationship, or from either side of a
    many-to-many relationship.

    It acts as a descriptor, managing the loading and manipulation of related
    objects.
    """

    def __init__(
        self,
        *,
        foreign_key_name: str,
        related_from: type[BaseModelType],
        **kwargs: Any,
    ) -> None:
        """
        Initializes a new RelatedField instance.

        Args:
            foreign_key_name (str): The name of the foreign key field on the
                                    `related_from` model that establishes this
                                    relationship.
            related_from (type[BaseModelType]): The model class that contains the
                                                foreign key pointing back to
                                                the `owner` of this RelatedField.
            **kwargs (Any): Additional keyword arguments passed to the
                            `RelationshipField` constructor.
        """
        self.foreign_key_name = foreign_key_name
        self.related_from = related_from
        super().__init__(
            # Do not inherit properties from parent fields.
            inherit=False,
            # Exclude this field from model serialization by default.
            exclude=True,
            # The field type is a list of instances of the related_from model.
            field_type=list[related_from],  # type: ignore
            # The annotation also reflects a list of related_from model instances.
            annotation=list[related_from],  # type: ignore
            # This field does not correspond directly to a database column type.
            column_type=None,
            # This field can be null, as related objects might not always exist.
            null=True,
            # Do not copy this field when duplicating a model instance.
            no_copy=True,
            **kwargs,
        )
        # Append SkipValidation metadata to bypass Pydantic's default validation.
        # Edgy implements its own extended validation logic for relationships.
        self.metadata.append(SkipValidation())
        # Append SkipJsonSchema metadata to temporarily skip JSON schema generation.
        # This is because the field's nature (e.g., M2M through model) might not be
        # fully determined at this stage.
        self.metadata.append(SkipJsonSchema())
        # If the related foreign key has a post-delete callback, set the
        # appropriate handler for this related field.
        if self.foreign_key.relation_has_post_delete_callback:
            self.post_delete_callback = self._notset_post_delete_callback

    @property
    def related_to(self) -> type[BaseModelType]:
        """
        Returns the model class that this RelatedField points to.
        This is typically the owner model of this RelatedField.

        Returns:
            type[BaseModelType]: The model class related to this field.
        """
        return self.owner

    @property
    def related_name(self) -> str:
        """
        Returns the name of this related field. This is usually the `related_name`
        defined on the ForeignKey or the automatically generated name.

        Returns:
            str: The name of the related field.
        """
        return self.name

    def to_model(
        self,
        field_name: str,
        value: Any,
    ) -> dict[str, Any]:
        """
        Converts the given value into a dictionary representation suitable for model
        instantiation or updates. This method handles the assignment of related
        instances to the field.

        Args:
            field_name (str): The name of the field to which the value is being
                              assigned.
            value (Any): The value to be converted, which can be an instance of
                         `ManyRelationProtocol`, a single model instance, or a
                         sequence of model instances.

        Returns:
            dict[str, Any]: A dictionary where the `field_name` is mapped to the
                            appropriate `ManyRelationProtocol` instance.
        """
        # Retrieve the current model instance from the context variable.
        instance = CURRENT_MODEL_INSTANCE.get()
        # If the value is already a ManyRelationProtocol, return it directly.
        if isinstance(value, ManyRelationProtocol):
            return {field_name: value}
        # If an instance exists (e.g., during an update or creation with related data).
        if instance:
            # Get the existing relation instance for this field on the current model.
            relation_instance = self.__get__(instance)
            # Ensure the value is a sequence, converting single instances to a list.
            if not isinstance(value, Sequence):
                value = [value]
            # Stage the provided values into the relation instance for later saving.
            relation_instance.stage(*value)
        else:
            # If no instance exists (e.g., loading from database), get a new
            # relation instance initialized with the provided references.
            relation_instance = self.get_relation(refs=value)
        # Return a dictionary with the field name mapped to the relation instance.
        return {field_name: relation_instance}

    def __get__(self, instance: BaseModelType, owner: Any = None) -> ManyRelationProtocol:
        """
        Descriptor method for accessing the related objects through this field.
        When `model_instance.related_field_name` is accessed, this method is called.
        It ensures that a `ManyRelationProtocol` instance is associated with the
        model instance for this field, allowing lazy loading and manipulation of
        related objects.

        Args:
            instance (BaseModelType): The instance of the model on which this
                                      RelatedField is being accessed.
            owner (Any): The owner class (model class). Unused in this context.

        Returns:
            ManyRelationProtocol: An object representing the many-to-many or
                                  one-to-many relationship, allowing access to
                                  related instances.

        Raises:
            ValueError: If `instance` is None, indicating a missing model instance.
        """
        # Ensure a model instance is provided.
        if not instance:
            raise ValueError("missing instance")

        # If the related field hasn't been initialized on the instance's dictionary.
        if instance.__dict__.get(self.name, None) is None:
            # Initialize it with a new relation obtained via get_relation.
            instance.__dict__[self.name] = self.get_relation()
        # If the relation instance itself doesn't have a reference to its parent.
        if instance.__dict__[self.name].instance is None:
            # Set the parent instance reference.
            instance.__dict__[self.name].instance = instance
        # Return the ManyRelationProtocol instance associated with this field.
        return instance.__dict__[self.name]  # type: ignore

    @functools.cached_property
    def foreign_key(self) -> BaseForeignKeyField:
        """
        Returns the `BaseForeignKeyField` instance that this `RelatedField`
        is effectively reversing. This property is cached for performance.

        Returns:
            BaseForeignKeyField: The foreign key field on the `related_from` model.
        """
        # Cast the field to BaseForeignKeyField as it's known to be a foreign key.
        return cast(BaseForeignKeyField, self.related_from.meta.fields[self.foreign_key_name])

    def traverse_field(self, path: str) -> tuple[Any, str, str]:
        """
        Traverses the field path in reverse, delegating the traversal to the
        underlying foreign key. This is used for complex query constructions
        involving related fields.

        Args:
            path (str): The path to traverse within the related field.

        Returns:
            tuple[Any, str, str]: A tuple containing the traversed field, the
                                  remaining path, and the original path segment.
        """
        return self.foreign_key.reverse_traverse_field(path)

    def get_relation(self, **kwargs: Any) -> ManyRelationProtocol:
        """
        Retrieves an instance of `ManyRelationProtocol` for this related field.
        This method typically handles the lazy loading of related objects.

        Args:
            **kwargs (Any): Additional keyword arguments to pass to the
                            `get_relation` method of the foreign key.

        Returns:
            ManyRelationProtocol: An object capable of managing the related
                                  collection of models.
        """
        return self.foreign_key.get_relation(**kwargs)

    def is_cross_db(self, owner_database: Database | None = None) -> bool:
        """
        Checks if the related model (through the foreign key) is in a different
        database than the owner model of this `RelatedField`.

        Args:
            owner_database (Database | None): The database instance of the
                                             owner model. If None, it defaults
                                             to the owner model's database.

        Returns:
            bool: True if the related model is in a different database, False otherwise.
        """
        # If no owner_database is provided, use the database of the owner model.
        if owner_database is None:
            owner_database = self.owner.database
        # Compare the URLs of the owner's database and the foreign key's owner's database.
        return str(owner_database.url) != str(self.foreign_key.owner.database.url)

    def get_related_model_for_admin(self) -> type[BaseModelType] | None:
        """
        Retrieves the related model class if it is registered within the
        admin models of its registry. This is primarily used for administrative
        interfaces to determine if a related model can be managed.

        Returns:
            type[BaseModelType] | None: The related model class if found in
                                        the admin registry, otherwise None.
        """
        # Assert that the registry exists and is not False.
        related_from_registry = self.related_from.meta.registry
        assert related_from_registry is not None and related_from_registry is not False
        # Check if the name of the related model is present in the admin models.
        if self.related_from.__name__ in related_from_registry.admin_models:
            # TODO: Handle embedded models specifically if needed.
            return self.related_from
        return None

    @property
    def is_m2m(self) -> bool:
        """
        Indicates whether this related field represents a many-to-many relationship.
        This determination is delegated to the underlying foreign key.

        Returns:
            bool: True if it's a many-to-many relationship, False otherwise.
        """
        return self.foreign_key.is_m2m

    def clean(self, name: str, value: Any, for_query: bool = False) -> dict[str, Any]:
        """
        Cleans and validates the given value for this related field,
        delegating the actual cleaning process to the reverse `clean` method
        of the underlying foreign key.

        Args:
            name (str): The name of the field being cleaned.
            value (Any): The value to be cleaned.
            for_query (bool): A flag indicating if the cleaning is for a database query.

        Returns:
            dict[str, Any]: A dictionary containing the cleaned value, typically
                            formatted for a query or model update.
        """
        return self.foreign_key.reverse_clean(name, value, for_query=for_query)

    def __repr__(self) -> str:
        """
        Returns a developer-friendly string representation of the RelatedField.
        """
        return f"<{type(self).__name__}: {self}>"

    def __str__(self) -> str:
        """
        Returns a human-readable string representation of the RelatedField,
        showing the related model and the name of the relationship.
        """
        return f"({self.related_to.__name__}={self.related_name})"

    async def post_save_callback(self, value: ManyRelationProtocol, is_update: bool) -> None:
        """
        An asynchronous callback executed after the owner model instance is saved.
        This method is responsible for saving any staged related objects.

        Args:
            value (ManyRelationProtocol): The instance managing the related objects.
            is_update (bool): A boolean indicating if the save operation was an update.
        """
        await value.save_related()

    async def _notset_post_delete_callback(self, value: ManyRelationProtocol) -> None:
        """
        An asynchronous callback executed after the owner model instance is deleted.
        This method delegates the post-delete handling to the related `ManyRelationProtocol`
        if it has a `post_delete_callback` method.

        Args:
            value (ManyRelationProtocol): The instance managing the related objects.
        """
        # Check if the ManyRelationProtocol instance has a post_delete_callback.
        if hasattr(value, "post_delete_callback"):
            # Await the post_delete_callback if it exists.
            await value.post_delete_callback()

    def reverse_clean(self, name: str, value: Any, for_query: bool = False) -> dict[str, Any]: ...
