import functools
from typing import TYPE_CHECKING, Any, Optional, Type, Union, cast

from edgy.core.db.fields.foreign_keys import BaseForeignKeyField
from edgy.core.db.fields.one_to_one_keys import BaseOneToOneKeyField

if TYPE_CHECKING:
    from edgy import Manager, Model, QuerySet, ReflectModel


class RelatedField:
    """
    When a `related_name` is generated, creates a RelatedField from the table pointed
    from the ForeignKey declaration and the the table declaring it.
    """

    def __init__(
        self,
        related_name: str,
        related_to: Union[Type["Model"], Type["ReflectModel"]],
        related_from: Optional[Union[Type["Model"], Type["ReflectModel"]]] = None,
        instance: Optional[Union[Type["Model"], Type["ReflectModel"]]] = None,
    ) -> None:
        self.related_name = related_name
        self.related_to = related_to
        self.related_from = related_from
        self.instance = instance

    @functools.cached_property
    def manager(self) -> "Manager":
        """Returns the manager class"""
        return cast("Manager", self.related_from.meta.manager)  # type: ignore

    @functools.cached_property
    def queryset(self) -> "QuerySet":
        return cast("QuerySet", self.manager.get_queryset())

    def m2m_related(self) -> Any:
        """
        Guarantees the the m2m filter is done by the owner of the call
        and not by the children.
        """
        if not self.related_from.meta.is_multi:  # type: ignore
            return

        related = [
            key
            for key, value in self.related_from.fields.items()  # type: ignore
            if key != self.related_to.__name__.lower() and isinstance(value, BaseForeignKeyField)
        ]
        return related

    def __get__(self, instance: Any, owner: Any) -> Any:
        return self.__class__(
            related_name=self.related_name,
            related_to=self.related_to,
            instance=instance,
            related_from=self.related_from,
        )

    def __getattr__(self, item: Any) -> Any:
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

    def get_foreign_key_field_name(self) -> str:
        """
        Table lookup for the given field containing the related field.

        If there is no field with the related_name declared, find the first field
        with the FK to the related_to.
        """
        field_name: Optional[str] = None
        for field, value in self.related_from.fields.items():  # type: ignore
            if isinstance(value, (BaseForeignKeyField, BaseOneToOneKeyField)):
                if value.related_name == self.related_name:
                    field_name = field
                    break
                elif not value.related_name or value.related_name is None:
                    field_name = field
                    break
        return cast("str", field_name)

    def wrap_args(self, func: Any) -> Any:
        @functools.wraps(func)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            field = self.get_foreign_key_field_name()
            kwargs[field] = self.instance.pk  # type: ignore

            related = self.m2m_related()
            if related:
                self.queryset.m2m_related = related[0]
            return func(*args, **kwargs)

        return wrapped

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self}>"

    def __str__(self) -> str:
        return f"({self.related_to.__name__}={self.related_name})"
