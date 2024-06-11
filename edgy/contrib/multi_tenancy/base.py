from typing import ClassVar

from edgy.contrib.multi_tenancy.metaclasses import BaseTenantMeta, TenantMeta
from edgy.core.db.models.model import Model


class TenantModel(Model, metaclass=BaseTenantMeta):
    """
    Base for a multi tenant model from the Edgy contrib.
    This is **not mandatory** and can be used as a possible
    out of the box solution for multi tenancy.

    This design is not meant to be "the one" but instead an
    example of how to achieve the multi-tenancy in a simple fashion
    using Edgy and Edgy models.
    """

    meta: ClassVar[TenantMeta] = TenantMeta(None, abstract=True)
