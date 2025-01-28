from __future__ import annotations

from typing import Any, ClassVar

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
from edgy.core.utils.models import create_edgy_model, generify_model_fields


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
        # registry = False, stops the retrieval of the registry from base classes
        registry = False

    @classmethod
    def generate_proxy_model(cls) -> type[Model]:
        """
        Generates a proxy model for each model. This proxy model is a simple
        shallow copy of the original model being generated.
        """
        # a proxy model is a copy of the model but without replaced field references and is not added to registry
        # it can't either

        # removes private pydantic stuff, except the prefixed ones
        attrs: dict[str, Any] = {
            key: val for key, val in cls.__dict__.items() if key not in cls._removed_copy_keys
        }
        # managers and fields are gone, we have to readd them with the correct data
        # Note: because it is not a real copy don't honor no_copy flags.
        attrs.update(cls.meta.fields)
        attrs.update(cls.meta.managers)
        attrs["__is_proxy_model__"] = True
        _copy = create_edgy_model(
            __name__=cls.__name__,
            __module__=cls.__module__,
            __definitions__=attrs,
            __metadata__=cls.meta,
            __bases__=cls.__bases__,
            # registry is still added because it is copied from meta
            __type_kwargs__={"skip_registry": True},
        )
        _copy.database = cls.database
        generify_model_fields(_copy)
        return _copy


class StrictModel(Model):
    model_config = ConfigDict(
        extra="forbid", arbitrary_types_allowed=True, validate_assignment=True, strict=True
    )

    class Meta:
        abstract = True
        # registry = False, stops the retrieval of the registry from base classes
        registry = False


class ReflectModel(ReflectedModelMixin, Model):
    """
    Reflect on async engines is not yet supported, therefore, we need to make a sync_engine
    call.
    """

    class Meta:
        abstract = True
        # registry = False, stops the retrieval of the registry from base classes
        registry = False
