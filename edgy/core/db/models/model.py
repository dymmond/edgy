from __future__ import annotations

import copy
import inspect
from typing import ClassVar, cast

from pydantic import ConfigDict

from edgy.core.db.models.base import EdgyBaseModel
from edgy.core.db.models.managers import Manager, RedirectManager
from edgy.core.db.models.metaclasses import BaseModelMeta, MetaInfo
from edgy.core.db.models.mixins import (
    DatabaseMixin,
    DeclarativeMixin,
    ModelRowMixin,
    ReflectedModelMixin,
)
from edgy.core.db.models.model_proxy import ProxyModel
from edgy.core.utils.models import generify_model_fields


class Model(
    ModelRowMixin, DeclarativeMixin, DatabaseMixin, EdgyBaseModel, metaclass=BaseModelMeta
):
    """
    Representation of an Edgy `Model`.

    This also means it can generate declarative SQLAlchemy models
    from anywhere by calling the `Model.declarative()` function.

    **Example**

    ```python
    import edgyBaseFieldType
    from edgy import Database, Registry

    database = Database("sqlite:///db.sqlite")
    models = Registry(database=database)


    class User(edgy.Model):
        '''
        The User model to be created in the database as a table
        If no name is provided the in Meta class, it will generate
        a "users" table for you.
        '''

        id: int = edgy.IntegerField(primary_key=True, autoincrement=True)
        is_active: bool = edgy.BooleanField(default=False)

        class Meta:
            registry = models
    ```
    """

    query: ClassVar[Manager] = Manager()
    query_related: ClassVar[RedirectManager] = RedirectManager(redirect_name="query")
    # registry = False, stops the retrieval of the registry from base classes
    meta: ClassVar[MetaInfo] = MetaInfo(None, abstract=True, registry=False)

    class Meta:
        abstract = True

    @classmethod
    def generate_proxy_model(cls) -> type[Model]:
        """
        Generates a proxy model for each model. This proxy model is a simple
        shallow copy of the original model being generated.
        """
        fields = {key: copy.copy(field) for key, field in cls.meta.fields.items()}

        class MethodHolder(Model):
            pass

        ignore = set(dir(MethodHolder))

        for key in dir(cls):
            if key in ignore or key.startswith("_"):
                continue
            val = inspect.getattr_static(cls, key)
            if inspect.isfunction(val):
                setattr(MethodHolder, key, val)

        proxy_model = ProxyModel(
            name=cls.__name__,
            module=cls.__module__,
            metadata=cls.meta,
            definitions=fields,
            bases=(MethodHolder,),
        )

        proxy_model.build()
        generify_model_fields(cast(type[EdgyBaseModel], proxy_model.model))
        return cast(type[Model], proxy_model.model)


class StrictModel(Model):
    model_config = ConfigDict(
        extra="forbid", arbitrary_types_allowed=True, validate_assignment=True, strict=True
    )


class ReflectModel(ReflectedModelMixin, Model):
    """
    Reflect on async engines is not yet supported, therefore, we need to make a sync_engine
    call.
    """

    model_config = ConfigDict(
        extra="allow", arbitrary_types_allowed=True, validate_assignment=True
    )

    class Meta:
        abstract = True
        # registry = False, stops the retrieval of the registry from base classes
        registry = False
