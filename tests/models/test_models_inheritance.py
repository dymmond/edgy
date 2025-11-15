from typing import ClassVar

import pytest

import edgy
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio

# here we don't initialize any database


def test_direct_descendant():
    models = edgy.Registry(DATABASE_URL)

    class Cat(edgy.StrictModel):
        class Meta:
            registry = models

        objects: ClassVar[edgy.Manager] = edgy.RedirectManager(redirect_name="query")

    Cat.proxy_model  # noqa: B018
    Cat.copy_edgy_model().proxy_model  # noqa: B018


def test_second_manager():
    models = edgy.Registry(DATABASE_URL)

    class DjangoBase(edgy.StrictModel):
        class Meta:
            abstract = True

        objects: ClassVar[edgy.Manager] = edgy.RedirectManager(redirect_name="query")

    class Cat(DjangoBase):
        class Meta:
            registry = models

        objects: ClassVar[edgy.Manager] = edgy.RedirectManager(redirect_name="query")

    class Cat2(Cat, DjangoBase):
        class Meta:
            registry = models

        objects2: ClassVar[edgy.Manager] = edgy.RedirectManager(redirect_name="query")

    Cat.proxy_model  # noqa: B018
    Cat.copy_edgy_model().proxy_model  # noqa: B018
    Cat2.proxy_model  # noqa: B018
    Cat2.copy_edgy_model().proxy_model  # noqa: B018
    DjangoBase.proxy_model  # noqa: B018
    DjangoBase.copy_edgy_model().proxy_model  # noqa: B018


def test_abstract_registry():
    models = edgy.Registry(DATABASE_URL)

    class DjangoBase(edgy.StrictModel):
        class Meta:
            abstract = True
            registry = models

        objects: ClassVar[edgy.Manager] = edgy.RedirectManager(redirect_name="query")

    class Cat(DjangoBase):
        objects: ClassVar[edgy.Manager] = edgy.RedirectManager(redirect_name="query")

    class Cat2(Cat, DjangoBase):
        objects2: ClassVar[edgy.Manager] = edgy.RedirectManager(redirect_name="query")

    assert "DjangoBase" not in models.models
    assert "Cat" in models.models
    assert "Cat2" in models.models

    Cat.proxy_model  # noqa: B018
    Cat.copy_edgy_model().proxy_model  # noqa: B018
    Cat2.proxy_model  # noqa: B018
    Cat2.copy_edgy_model().proxy_model  # noqa: B018
    DjangoBase.proxy_model  # noqa: B018
    DjangoBase.copy_edgy_model().proxy_model  # noqa: B018
