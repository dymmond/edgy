from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

import edgy
from edgy.core.db.context_vars import CURRENT_MODEL_INSTANCE, CURRENT_PHASE
from edgy.core.db.fields.base import BaseField
from edgy.core.db.fields.factories import ForeignKeyFieldFactory
from edgy.exceptions import ModelReferenceError
from edgy.utils.compat import is_class_and_subclass

if TYPE_CHECKING:
    from edgy.core.db.fields.types import BaseFieldType
    from edgy.core.db.models.model_reference import ModelRef
    from edgy.core.db.models.types import BaseModelType


class BaseRefForeignKey(BaseField):
    """
    Base class for a foreign key field that references a ModelRef.
    This class is primarily used for type hinting and establishing the
    inheritance hierarchy for `RefForeignKey`.
    """


class RefForeignKey(ForeignKeyFieldFactory, list):
    """
    A specialized foreign key field designed to work with `ModelRef` classes.

    This field allows a model to establish a relationship with a `ModelRef`,
    which represents a reference to another model without necessarily defining
    a direct foreign key column in the database. It is particularly useful
    for handling generic relationships or when the related model's details
    are managed through a separate "through" model or a `ModelRef`.

    It enforces that the `to` argument is an instance of `ModelRef` and that
    the `ModelRef` subclass has a `__related_name__` defined.

    Attributes:
        field_type (list): The Python type representing the field (always `list`),
                           as it can hold a list of `ModelRef` instances.
        field_bases (tuple): The base classes for this field, including `BaseRefForeignKey`.
    """

    field_type = list
    field_bases = (BaseRefForeignKey,)

    @classmethod
    def modify_input(
        cls,
        field_obj: BaseFieldType,
        name: str,
        kwargs: dict[str, Any],
        original_fn: Any = None,
    ) -> None:
        """
        Modifies the input `kwargs` during model initialization.

        If the field name is not present in `kwargs` and the phase is `init_db`,
        it initializes the field with an empty list. This ensures that the field
        is always a list, ready to store `ModelRef` instances.
        """
        phase = CURRENT_PHASE.get()
        # If the field is not in kwargs and we are in the 'init_db' phase,
        # initialize it as an empty list.
        if name not in kwargs and phase == "init_db":
            kwargs[name] = []

    def embed_field(
        self,
        prefix: str,
        new_fieldname: str,
        owner: type[BaseModelType] | None = None,
        parent: BaseFieldType | None = None,
    ) -> BaseFieldType | None:
        """
        Placeholder for embedding logic. `RefForeignKey` typically does not
        embed directly into queries in the same way as traditional foreign keys,
        as its values are often handled through the associated `__related_name__`.
        """
        return None

    def __new__(cls, to: ModelRef, null: bool = False) -> BaseFieldType:
        """
        Creates a new `RefForeignKey` instance.

        Args:
            to (ModelRef): The `ModelRef` class that this foreign key references.
                           This must be a subclass of `edgy.ModelRef`.
            null (bool): Whether the field can be null in the database. Defaults to `False`.

        Returns:
            BaseFieldType: The constructed `RefForeignKey` instance.

        Raises:
            ModelReferenceError: If `to` is not a `ModelRef` or if the `ModelRef`
                                 does not have a `__related_name__` defined.
        """
        # Validate that 'to' is a subclass of edgy.ModelRef.
        if not is_class_and_subclass(to, edgy.ModelRef):
            raise ModelReferenceError(
                detail="A model reference must be an object of type ModelRef"
            )
        # Validate that the ModelRef has a __related_name__ defined.
        # This related name points to the actual relationship field on the owner model.
        if not getattr(to, "__related_name__", None):
            raise ModelReferenceError(
                "'__related_name__' must be declared when subclassing ModelRef."
            )

        # Initialize the field. It's excluded from database columns (`exclude=True`)
        # as it represents a logical relationship handled by the `ModelRef` and its
        # associated `__related_name__` field (which might be a ManyToManyField or ForeignKey).
        return super().__new__(cls, to=to, exclude=True, null=null)

    @classmethod
    async def post_save_callback(
        cls,
        field_obj: BaseFieldType,
        value: list | None,
        is_update: bool,
        original_fn: Any = None,
    ) -> None:
        """
        Asynchronous post-save callback for `RefForeignKey`.

        This callback is executed after a model instance containing this field is saved.
        It processes the list of `ModelRef` instances provided in `value` and
        establishes the actual relationships by adding them to the related field
        (determined by the `__related_name__` on the `ModelRef`).

        Args:
            field_obj (BaseFieldType): The field object itself.
            value (list | None): The list of `ModelRef` instances or dictionaries
                                 representing the related models to be associated.
            is_update (bool): `True` if the operation is an update, `False` for an insert.
            original_fn (Any): The original callback function (if any).
        """
        instance = CURRENT_MODEL_INSTANCE.get()
        if not value:
            return

        model_ref = field_obj.to
        # Get the actual relationship field on the instance's meta.
        relation_field = instance.meta.fields[model_ref.__related_name__]
        extra_params = {}

        try:
            # Determine the target model class.
            # This handles both ManyToMany and ForeignKey relationships.
            target_model_class = relation_field.target
        except AttributeError:
            # For reverse relationships (e.g., reverse ManyToMany), get from related_from.
            target_model_class = relation_field.related_from

        # If it's not a Many-to-Many relationship (i.e., a ForeignKey),
        # prepare to set the foreign key on the target model.
        if not relation_field.is_m2m:
            extra_params[relation_field.foreign_key.name] = instance

        # Get the actual relation object from the instance (e.g., a ManyRelation or one-to-one).
        relation = getattr(instance, model_ref.__related_name__)

        # Process each item in the value list.
        while value:
            instance_or_dict: dict | ModelRef = value.pop()
            # If it's a dictionary, convert it to a ModelRef instance.
            if isinstance(instance_or_dict, dict):
                instance_or_dict = model_ref(**instance_or_dict)

            # Create an instance of the target model class from the ModelRef data.
            # Exclude '__related_name__' from the model_dump as it's an internal ModelRef attribute.
            model = target_model_class(
                **cast("ModelRef", instance_or_dict).model_dump(exclude={"__related_name__"}),
                **extra_params,  # Add foreign key if applicable.
            )
            # Add the created model to the relation. This persists the relationship.
            await relation.add(model)
