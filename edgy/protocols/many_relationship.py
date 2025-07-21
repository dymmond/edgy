from typing import TYPE_CHECKING, Any, Optional, Protocol, runtime_checkable

# TYPE_CHECKING is used to prevent circular imports during runtime while
# allowing type checkers to see the correct types.
if TYPE_CHECKING:  # pragma: nocover
    from edgy.core.db.models.types import BaseModelType


@runtime_checkable
class ManyRelationProtocol(Protocol):
    """
    Defines the interface for managing 'many' side of a relationship in Edgy models.

    This protocol specifies the methods that must be implemented by any class
    that handles a "many" relationship (e.g., one-to-many, many-to-many) between
    Edgy models. It ensures a consistent API for operations such as saving,
    creating, adding, staging, and removing related instances.

    Classes implementing this protocol are expected to manage a collection of
    related `BaseModelType` instances associated with a primary `instance`.
    The `@runtime_checkable` decorator allows for runtime checks using `isinstance()`.
    """

    instance: "BaseModelType"
    """
    The primary model instance to which this many-relation manager is attached.
    This is the "one" side of a one-to-many relationship or one side of a
    many-to-many relationship from the perspective of this manager.
    """

    async def save_related(self) -> None:
        """
        Asynchronously saves all staged or modified related instances.

        This method is responsible for persisting any changes made to the
        related models managed by this protocol implementation. It should
        handle the necessary database operations to ensure consistency.
        """
        ...

    async def create(self, *args: Any, **kwargs: Any) -> Optional["BaseModelType"]:
        """
        Asynchronously creates a new related model instance and associates it
        with the primary instance.

        This method should handle the creation of a new record in the database
        for the related model type and establish the necessary link back to
        the `instance` model.

        Parameters:
            *args (Any): Positional arguments to pass to the related model's
                         creation method.
            **kwargs (Any): Keyword arguments to pass to the related model's
                            creation method.

        Returns:
            Optional[BaseModelType]: The newly created and associated related
                                     model instance, or `None` if creation fails
                                     or is not applicable.
        """
        ...

    async def add(self, child: "BaseModelType") -> Optional["BaseModelType"]:
        """
        Asynchronously adds an existing related model instance to the collection
        associated with the primary instance.

        This method establishes a relationship between the `instance` and the
        provided `child` model, typically by updating foreign keys or creating
        entries in an intermediary table for many-to-many relationships.

        Parameters:
            child (BaseModelType): The existing related model instance to add.

        Returns:
            Optional[BaseModelType]: The added child model instance, or `None`
                                     if the operation fails or is not applicable.
        """
        ...

    def stage(self, *children: "BaseModelType") -> None:
        """
        Stages one or more related model instances for later addition or saving.

        This method provides a "lazy add" mechanism, allowing instances to be
        prepared for association without immediately performing database operations.
        The actual persistence or relationship establishment typically occurs
        when `save_related` is called.

        Parameters:
            *children (BaseModelType): One or more related model instances to stage.
        """
        ...

    async def remove(self, child: Optional["BaseModelType"] = None) -> None:
        """
        Asynchronously removes a specific related model instance or all related
        instances from the association with the primary instance.

        If a `child` is provided, only that specific relationship is severed.
        If `child` is `None`, all relationships managed by this protocol
        instance are removed. This method should handle the necessary database
        operations to break the association without necessarily deleting the
        related model records themselves (unless cascading deletes are configured
        at the database level).

        Parameters:
            child (Optional[BaseModelType]): The specific related model instance
                                             to remove. If `None`, all related
                                             instances are removed. Defaults to `None`.
        """
        ...
