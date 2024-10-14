from typing import TYPE_CHECKING, Any, Optional, Union, cast

from edgy.core.db.querysets.base import QuerySet

if TYPE_CHECKING:
    from edgy.core.db.models.base import BaseModelType


class BaseManager:
    def __init__(
        self,
        *,
        owner: Optional[Union[type["BaseModelType"]]] = None,
        inherit: bool = True,
        name: str = "",
        instance: Optional[Union["BaseModelType"]] = None,
    ):
        self.owner = owner
        self.inherit = inherit
        self.name = name
        self.instance = instance

    @property
    def model_class(self) -> Any:
        # legacy name
        return self.owner

    def get_queryset(self) -> QuerySet:
        """
        Returns the queryset object.
        """
        raise NotImplementedError(
            f"The {self!r} manager doesn't implement the get_queryset method."
        )


class Manager(BaseManager):
    """
    Base Manager for the Edgy Models.
    To create a custom manager, the best approach is to inherit from the ModelManager.

    **Example**

    ```python
    from saffier.managers import ModelManager
    from saffier.models import Model


    class MyCustomManager(ModelManager): ...


    class MyOtherManager(ModelManager): ...


    class MyModel(saffier.Model):
        query = MyCustomManager()
        active = MyOtherManager()

        ...
    ```
    """

    def get_queryset(self) -> "QuerySet":
        """
        Returns the queryset object.

        Checks for a global possible tenant and returns the corresponding queryset.
        """
        assert self.owner is not None
        if self.instance is not None:
            using_schema = self.instance.__using_schema__
            database = self.instance.database
        else:
            using_schema = self.owner.__using_schema__
            database = self.owner.database
        return QuerySet(self.owner, using_schema=using_schema, database=database)

    def __getattr__(self, name: str) -> Any:
        """
        Gets the attribute from the queryset and if it does not
        exist, then lookup in the model.
        """
        if name.startswith("_") or name == self.name:
            return super().__getattr__(name)
        try:
            # we need to check tenant every request
            return getattr(self.get_queryset(), name)
        except AttributeError:
            return getattr(self.owner, name)


class RedirectManager(BaseManager):
    def __init__(self, *, redirect_name: str, **kwargs: Any):
        self.redirect_name = redirect_name
        super().__init__(**kwargs)

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_") or name == self.name:
            return super().__getattr__(name)
        return getattr(self.owner.meta.managers[self.redirect_name], name)

    def get_queryset(self) -> "QuerySet":
        return cast("QuerySet", self.__getattr__("get_queryset")())
