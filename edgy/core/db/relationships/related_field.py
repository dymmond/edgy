import functools
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple, Type, Union, cast

from edgy.core.db.fields.base import BaseField
from edgy.core.db.fields.foreign_keys import BaseForeignKeyField
from edgy.core.db.relationships.relation import SingleRelation

if TYPE_CHECKING:
    from edgy import Model, ReflectModel

class RelatedField(BaseField):
    """
    When a `related_name` is generated, creates a RelatedField from the table pointed
    from the ForeignKey declaration and the the table declaring it.
    """

    def __init__(
        self,
        *,
        foreign_key_name: str,
        related_from: Union[Type["Model"], Type["ReflectModel"]],
        embed_parent: Optional[Tuple[str, str]]=None,
        **kwargs: Any
    ) -> None:
        self.foreign_key_name = foreign_key_name
        self.related_from = related_from
        self.embed_parent = embed_parent
        super().__init__(
            inherit=False,
            exclude=True,
            deprecated=False,
            __type__=Any,
            annotation=Any,
            column_type=None,
            null=True,
            **kwargs
        )

    @property
    def related_to(self) ->  Union[Type["Model"], Type["ReflectModel"]]:
        return self.owner

    @property
    def related_name(self) ->  str:
        return self.name

    def to_model(self, field_name: str, value: Any, phase: str = "") -> Dict[str, Any]:
        """
        Meta field
        """
        return {field_name: SingleRelation(to=self.related_from, to_foreign_key=self.foreign_key_name, embed_parent=self.embed_parent, refs=value)}

    def __get__(self, instance: "Model", owner: Any = None) -> SingleRelation:
        if instance:
            if self.name not in instance.__dict__:
                instance.__dict__[self.name] = SingleRelation(to=self.related_from, to_foreign_key=self.foreign_key_name, embed_parent=self.embed_parent, instance=instance)
            if instance.__dict__[self.name].instance is None:
                instance.__dict__[self.name].instance = instance
            return instance.__dict__[self.name]  # type: ignore
        raise ValueError("missing instance")

    def __set__(self, instance: "Model", value: Any) -> None:
        relation = self.__get__(instance)
        if not isinstance(value, Sequence):
            value = [value]
        for v in value:
            relation._add_object(v)

    @functools.cached_property
    def foreign_key(self) -> BaseForeignKeyField:
        return cast(BaseForeignKeyField, self.related_from.meta.fields_mapping[self.foreign_key_name])

    @property
    def is_cross_db(self) -> bool:
        return self.foreign_key.is_cross_db

    def clean(self, name: str, value: Any, for_query: bool = False) -> Dict[str, Any]:
        if not for_query:
            return {}
        return self.related_to.meta.pk.clean("pk", value, for_query=for_query)  # type: ignore

    def wrap_args(self, func: Any) -> Any:
        @functools.wraps(func)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            # invert, so use the foreign_key_name
            # will be parsed later
            query: Dict[str, Any] = {}
            for column_name in self.foreign_key.get_column_names():
                related_name = self.foreign_key.from_fk_field_name(self.foreign_key_name, column_name)
                query[related_name] = getattr(self.instance, related_name)
            kwargs[self.foreign_key_name] =  query

            self.queryset.embed_parent = self.embed_parent
            return func(*args, **kwargs)

        return wrapped

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self}>"

    def __str__(self) -> str:
        return f"({self.related_to.__name__}={self.related_name})"
