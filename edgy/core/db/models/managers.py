from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from edgy.core.db.querysets.base import QuerySet

if TYPE_CHECKING:
    from edgy.core.db.models.base import BaseModelType


class BaseManager:
    def __init__(
        self,
        *,
        owner: type[BaseModelType] | None = None,
        inherit: bool = True,
        name: str = "",
        instance: BaseModelType | None = None,
    ) -> None:
        """
        Initializes the BaseManager.

        Args:
            owner (type[BaseModelType] | None): The owner model class associated
                                                  with this manager. Defaults to None.
            inherit (bool): A boolean indicating whether the manager should be
                            inherited by subclasses. Defaults to True.
            name (str): The name of the manager instance. Defaults to an empty string.
            instance (BaseModelType | None): The model instance associated with
                                             this manager, if it's an instance manager.
                                             Defaults to None.
        """
        self.owner = owner
        self.inherit = inherit
        self.name = name
        self.instance = instance

    @property
    def model_class(self) -> Any:
        """
        Provides a legacy name for the owner property.

        Returns:
            Any: The owner model class.
        """
        # This property serves as a legacy name for 'owner'.
        return self.owner

    def get_queryset(self) -> QuerySet:
        """
        Abstract method to be implemented by subclasses to return a QuerySet object.

        Raises:
            NotImplementedError: This method must be implemented by concrete manager
                                 subclasses.
        """
        raise NotImplementedError(
            f"The {self!r} manager doesn't implement the get_queryset method."
        )


class Manager(BaseManager):
    """
    A concrete implementation of BaseManager, serving as the default manager for Edgy Models.

    This manager provides the core functionality for querying model instances.
    Custom managers should inherit from this class to extend or modify query behavior.

    Example:
        ```python
        from edgy import Manager, Model


        class MyCustomManager(Manager):
            # Custom manager logic can be added here
            pass


        class MyOtherManager(Manager):
            # Another custom manager
            pass


        class MyModel(Model):
            query = MyCustomManager()  # Assigning a custom manager
            active = MyOtherManager()  # Assigning another custom manager

            # ... model fields and other definitions
        ```
    """

    def get_queryset(self) -> QuerySet:
        """
        Returns a QuerySet object tailored for the manager's owner model.

        This method determines the appropriate schema and database to use for the queryset,
        considering whether the manager is bound to a model class or a specific instance.

        Returns:
            QuerySet: An instance of QuerySet configured for the owner model.
        """
        # Ensure that the owner is set before attempting to create a queryset.
        assert self.owner is not None

        # Determine the `using_schema` and `database` based on whether the manager
        # is associated with an instance or a class.
        if self.instance is not None:
            # If an instance is present, use its schema and database.
            using_schema = self.instance.__using_schema__
            database = self.instance.database
        else:
            # Otherwise, use the owner class's schema and database.
            using_schema = self.owner.__using_schema__
            database = self.owner.database

        # Return a new QuerySet initialized with the owner, schema, and database.
        return QuerySet(self.owner, using_schema=using_schema, database=database)

    def __getattr__(self, name: str) -> Any:
        """
        Provides dynamic attribute access, prioritizing queryset methods and then
        falling back to model attributes.

        This allows direct calls to queryset methods (like `filter`, `get`, `all`)
        on the manager instance. If an attribute is not found on the queryset,
        it attempts to retrieve it from the owner model class.

        Args:
            name (str): The name of the attribute being accessed.

        Returns:
            Any: The retrieved attribute or method.

        Raises:
            AttributeError: If the attribute does not exist on either the queryset
                            or the owner model.
        """
        # Prevent infinite recursion and access to internal attributes or the manager's own name.
        if name.startswith("_") or name == self.name:
            return super().__getattr__(name)
        try:
            # Attempt to get the attribute from the queryset first. This allows
            # methods like .filter(), .get() to be called directly on the manager.
            return getattr(self.get_queryset(), name)
        except AttributeError:
            # If the attribute is not found on the queryset, try to get it from the owner model.
            return getattr(self.owner, name)


class RedirectManager(BaseManager):
    """
    A manager that redirects attribute access to another named manager within the
    same model's meta options.

    This is useful for creating aliases or providing different entry points to the
    same underlying manager functionality, or for specific use cases where
    manager methods need to be proxied.
    """

    def __init__(self, *, redirect_name: str, **kwargs: Any) -> None:
        """
        Initializes the RedirectManager.

        Args:
            redirect_name (str): The name of the manager to which calls should be
                                 redirected. This manager must exist in the owner
                                 model's `meta.managers` dictionary.
            **kwargs (Any): Arbitrary keyword arguments passed to the `BaseManager`
                            constructor.
        """
        self.redirect_name = redirect_name
        super().__init__(**kwargs)

    def __getattr__(self, name: str) -> Any:
        """
        Redirects attribute access to the manager specified by `redirect_name`.

        This method intercepts any attribute access on the `RedirectManager` instance
        and forwards it to the target manager.

        Args:
            name (str): The name of the attribute being accessed.

        Returns:
            Any: The retrieved attribute from the redirected manager.

        Raises:
            AttributeError: If the attribute does not exist on the redirected manager.
        """
        # Prevent infinite recursion and access to internal attributes or the manager's own name.
        if name.startswith("_") or name == self.name:
            return super().__getattr__(name)

        # Access the target manager via the owner's meta managers and return its attribute.
        # This assumes the owner and the target manager are correctly set up.
        return getattr(self.owner.meta.managers[self.redirect_name], name)

    def get_queryset(self) -> QuerySet:
        """
        Retrieves the queryset by calling the `get_queryset` method on the redirected manager.

        This ensures that the `get_queryset` call is also proxied to the target manager,
        maintaining consistent redirection behavior.

        Returns:
            QuerySet: The queryset returned by the redirected manager's `get_queryset` method.
        """
        # Cast the result to QuerySet as __getattr__ returns Any.
        return cast("QuerySet", self.__getattr__("get_queryset")())
