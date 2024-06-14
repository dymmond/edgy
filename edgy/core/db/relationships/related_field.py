import functools
from typing import TYPE_CHECKING, Any, Dict, Optional, Type, Union, cast

from edgy.core.db.fields.foreign_keys import BaseForeignKeyField
from edgy.core.db.models.utils import pk_from_model

if TYPE_CHECKING:
    from edgy import Manager, Model, QuerySet, ReflectModel


class RelatedField:
    """
    When a `related_name` is generated, creates a RelatedField from the table pointed
    from the ForeignKey declaration and the the table declaring it.
    """

    def __init__(
        self,
        foreign_key_name: str,
        related_name: str,
        related_to: Union[Type["Model"], Type["ReflectModel"]],
        related_from: Union[Type["Model"], Type["ReflectModel"]],
        instance: Optional[Union["Model", "ReflectModel"]] = None,
    ) -> None:
        self.foreign_key_name = foreign_key_name
        self.related_name = related_name
        self.related_to = related_to
        self.related_from = related_from
        self.instance = instance

    @functools.cached_property
    def manager(self) -> "Manager":
        """Returns the manager class"""
        manager: Optional["Manager"] = getattr(self.related_from, "query_related", None)
        if manager is None:
            manager = self.related_from.query
        return manager

    @functools.cached_property
    def queryset(self) -> "QuerySet":
        return self.manager.get_queryset()

    @functools.cached_property
    def foreign_key(self) -> BaseForeignKeyField:
        return cast(BaseForeignKeyField, self.related_from.meta.fields_mapping[self.foreign_key_name])

    @property
    def is_cross_db(self) -> bool:
        return self.foreign_key.is_cross_db

    def m2m_related(self) -> Any:
        """
        Guarantees the the m2m filter is done by the owner of the call
        and not by the children.
        """
        if not self.related_from.meta.is_multi:
            return

        related = [
            key
            for key, value in self.related_from.fields.items()
            if key != self.related_to.__name__.lower() and isinstance(value, BaseForeignKeyField)
        ]
        return related

    def __get__(self, instance: Any, owner: Any = None) -> Any:
        return self.__class__(
            foreign_key_name=self.foreign_key_name,
            related_name=self.related_name,
            related_to=self.related_to,
            instance=instance,
            related_from=self.related_from,
        )

    def __getattr__(self, item: str) -> Any:
        """
        Gets the attribute from the queryset and if it does not
        exist, then lookup in the model.
        """
        try:
            attr = getattr(self.queryset, item)
        except AttributeError:
            attr = getattr(self.related_from, item)

        func = self.wrap_args(attr)
        return func

    def clean(self, name: str, value: Any, for_query: bool = False) -> Dict[str, Any]:
        return self.related_to.meta.pk.clean("pk", value, for_query=for_query)  # type: ignore

    def wrap_args(self, func: Any) -> Any:
        @functools.wraps(func)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            # invert, so use the foreign_key_name
            # will be parsed later
            kwargs[self.foreign_key_name] = pk_from_model(self.instance, always_dict=True)

            related = self.m2m_related()
            if related:
                self.queryset.m2m_related = related[0]
            return func(*args, **kwargs)

        return wrapped

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self}>"

    def __str__(self) -> str:
        return f"({self.related_to.__name__}={self.related_name})"
