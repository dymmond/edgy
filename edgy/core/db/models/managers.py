from typing import Any

from edgy.core.db.context_vars import get_tenant, set_tenant
from edgy.core.db.querysets.base import QuerySet


class Manager:
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

    def __init__(self, model_class: Any = None, inherit: bool=True, name: str = "", instance: Any=None):
        self.model_class = model_class
        self.inherit = inherit
        self.name = name
        self.instance = instance

    def get_queryset(self) -> "QuerySet":
        """
        Returns the queryset object.

        Checks for a global possible tenant and returns the corresponding queryset.
        """
        tenant = get_tenant()
        if tenant:
            set_tenant(None)
            return QuerySet(
                self.model_class,
                table=self.model_class.table_schema(tenant),  # type: ignore
            )
        return QuerySet(self.model_class)

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
            return getattr(self.model_class, name)
