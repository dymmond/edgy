from __future__ import annotations

from functools import cached_property
from typing import TYPE_CHECKING, Any, cast

from pydantic.json_schema import WithJsonSchema

from edgy.core.db.constants import CASCADE
from edgy.core.db.context_vars import CURRENT_FIELD_CONTEXT, CURRENT_MODEL_INSTANCE
from edgy.core.db.fields.foreign_keys import BaseForeignKeyField, ForeignKey
from edgy.core.db.relationships.relation import SingleRelation
from edgy.core.terminal import Print
from edgy.protocols.many_relationship import ManyRelationProtocol

if TYPE_CHECKING:
    from edgy.core.db.fields.types import BaseFieldType
    from edgy.core.db.models.types import BaseModelType

# Initialize a Print instance for terminal output, likely for warnings.
terminal = Print()


class BaseContentTypeField(BaseForeignKeyField):
    """
    Base class for ContentTypeField, extending BaseForeignKeyField.

    This class provides the core logic and behaviors specific to content type
    relationships, including schema handling and relationship management.
    """

    def __init__(
        self,
        **kwargs: Any,
    ) -> None:
        """
        Initializes the BaseContentTypeField.

        Args:
            **kwargs (Any): Arbitrary keyword arguments passed to the
                            `BaseForeignKeyField` constructor.
        """
        super().__init__(**kwargs)
        # Append a JSON schema for validation, typically used in serialization.
        self.metadata.append(WithJsonSchema(mode="validation", json_schema=None))

    async def pre_save_callback(
        self, value: Any, original_value: Any, is_update: bool
    ) -> dict[str, Any]:
        """
        A callback executed before saving the field's value.

        This method ensures that if the content type value is an Edgy Model
        instance (or its proxy), its name and schema are correctly set
        based on the owner model.

        Args:
            value (Any): The current value of the field.
            original_value (Any): The original value of the field before modification.
            is_update (bool): A boolean indicating if the operation is an update.

        Returns:
            dict[str, Any]: The processed value and potentially other updates for saving.
        """
        # Retrieve the current model instance from the context variable.
        instance = CURRENT_MODEL_INSTANCE.get()
        target = self.target
        # If the value is None or an empty dictionary, revert to the original value.
        if value is None or (isinstance(value, dict) and not value):
            value = original_value
        # Check if the value is an instance of the target model or its proxy.
        if isinstance(value, target | target.proxy_model):
            # Set the name of the content type instance to the owner model's name.
            value.name = self.owner.__name__
            # Set the schema name for the content type instance based on the
            # currently active instance's schema.
            value.schema_name = instance.get_active_instance_schema()
        # Call the parent's pre_save_callback to continue the saving process.
        return await super().pre_save_callback(value, original_value, is_update=is_update)

    def get_relation(self, **kwargs: Any) -> ManyRelationProtocol:
        """
        Returns the relationship object for this field.

        If a `relation_fn` is defined, it is used; otherwise, a `SingleRelation`
        is created.

        Args:
            **kwargs (Any): Arbitrary keyword arguments for the relation.

        Returns:
            ManyRelationProtocol: The relationship instance.
        """
        if self.relation_fn is not None:
            return self.relation_fn(**kwargs)
        # Return a SingleRelation, indicating a one-to-one or many-to-one relationship.
        return cast(
            ManyRelationProtocol,
            SingleRelation(
                to=self.owner, to_foreign_key=self.name, embed_parent=self.embed_parent, **kwargs
            ),
        )

    @cached_property
    def reverse_name(self) -> str:
        """
        Returns the calculated reverse name for the relationship.

        This name is used to access the related content type object from
        the target model.

        Returns:
            str: The reverse name, e.g., "reverse_owner_model_name".
        """
        return f"reverse_{self.owner.__name__.lower()}"

    @cached_property
    def related_name(self) -> str:
        """
        Returns the calculated related name for the relationship.

        This is typically the same as `reverse_name` for consistency.

        Returns:
            str: The related name, e.g., "reverse_owner_model_name".
        """
        return f"reverse_{self.owner.__name__.lower()}"


def default_fn() -> Any:
    """
    Default function to generate the content type instance.

    This function retrieves the owner model from the current field context
    and uses the registry to create a content type instance with the
    owner's name.
    """
    # Get the owner model from the current field context.
    owner = CURRENT_FIELD_CONTEXT.get()["field"].owner
    # Create a content type instance using the registry, providing the owner's name.
    # The schema parameter is also set in the pre_save_callbacks.
    return owner.meta.registry.content_type(name=owner.__name__)


class ContentTypeField(ForeignKey):
    """
    A specific type of ForeignKey field used for managing generic foreign keys
    to content types (models).

    This field automatically handles the `related_name`, `reverse_name`,
    `unique`, and `null` properties to ensure proper content type
    relationship behavior.
    """

    field_bases = (BaseContentTypeField,)

    def __new__(
        cls,
        to: type[BaseModelType] | str = "ContentType",
        on_delete: str = CASCADE,
        no_constraint: bool = False,
        remove_referenced: bool = True,
        default: Any = default_fn,
        **kwargs: Any,
    ) -> BaseFieldType:
        """
        Creates a new ContentTypeField instance.

        Args:
            to (type[BaseModelType] | str, optional): The target model
                                                      for the foreign key.
                                                      Defaults to "ContentType".
            on_delete (str, optional): The action to perform on deletion of
                                       the referenced object. Defaults to `CASCADE`.
            no_constraint (bool, optional): If `True`, no foreign key
                                            constraint is created in the database.
                                            Defaults to `False`.
            remove_referenced (bool, optional): If `True`, when a content type
                                                is removed, it also removes the
                                                referenced object. Defaults to `True`.
            default (Any, optional): The default value for the field.
                                     Defaults to `default_fn`.
            **kwargs (Any): Arbitrary keyword arguments.

        Returns:
            BaseFieldType: The new ContentTypeField instance.
        """
        return super().__new__(
            cls,
            to=to,
            default=default,
            on_delete=on_delete,
            no_constraint=no_constraint,
            remove_referenced=remove_referenced,
            **kwargs,
        )

    @classmethod
    def validate(cls, kwargs: dict[str, Any]) -> None:
        """
        Validates the keyword arguments provided to the ContentTypeField.

        This method specifically warns about and removes arguments that are
        automatically managed by ContentTypeField (`related_name`, `reverse_name`,
        `unique`, `null`) to prevent unintended overrides.
        It also enforces `unique=True` and `null=False`.

        Args:
            kwargs (dict[str, Any]): The keyword arguments to validate.
        """
        for argument in ["related_name", "reverse_name", "unique", "null"]:
            if kwargs.get(argument):
                # Issue a warning if an argument that is automatically handled
                # by ContentTypeField is explicitly declared.
                terminal.write_warning(
                    f"Declaring `{argument}` on a ContentTypeField has no effect."
                )
        # Remove these arguments as they are internally managed.
        kwargs.pop("related_name", None)
        kwargs.pop("reverse_name", None)
        # Enforce unique and not null for content type fields.
        kwargs["unique"] = True
        kwargs["null"] = False
        # Call the parent's validate method to perform further validation.
        super().validate(kwargs)
