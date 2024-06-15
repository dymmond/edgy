from typing import TYPE_CHECKING, Any, Optional, Type, Union

from edgy.core.db.context_vars import get_tenant, set_tenant
from edgy.core.db.querysets.base import QuerySet

if TYPE_CHECKING:
    from edgy.core.db.models.base import EdgyBaseModel

class BaseManager:
    def __init__(self, owner: Optional[Union[Type["EdgyBaseModel"]]] = None, inherit: bool=True, name: str = "", instance: Optional[Union["EdgyBaseModel"]]=None):
        self.owner = owner
        self.inherit = inherit
        self.name = name
        self.instance = instance

    @property
    def model_class(self) -> Any:
        # legacy name
        return self.owner


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
        tenant = get_tenant()
        if tenant:
            set_tenant(None)
            return QuerySet(
                self.owner,
                table=self.owner.table_schema(tenant),  # type: ignore
            )
        return QuerySet(self.owner)

    def __getattr__(self, name: str) -> Any:
        """
        Gets the attribute from the queryset and if it does not
        exist, then lookup in the model.
        """
        if name.startswith("_"):
            return super().__getattr__(name)
        try:
            return getattr(self.get_queryset(), name)
        except AttributeError:
            return getattr(self.owner, name)
