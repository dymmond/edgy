import functools
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Dict, Tuple, Type, Union, cast

from edgy.core.db.fields.base import RelationshipField
from edgy.core.db.fields.foreign_keys import BaseForeignKeyField
from edgy.protocols.many_relationship import ManyRelationProtocol

if TYPE_CHECKING:
    from edgy import Model, ReflectModel

class RelatedField(RelationshipField):
    """
    When a `related_name` is generated, creates a RelatedField from the table pointed
    from the ForeignKey declaration and the the table declaring it.
    """

    def __init__(
        self,
        *,
        foreign_key_name: str,
        related_from: Union[Type["Model"], Type["ReflectModel"]],
        **kwargs: Any
    ) -> None:
        self.foreign_key_name = foreign_key_name
        self.related_from = related_from
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
        if isinstance(value, ManyRelationProtocol):
            return {field_name: value}
        return {field_name: self.get_relation(refs=value)}

    def __get__(self, instance: "Model", owner: Any = None) -> ManyRelationProtocol:
        if instance:
            if self.name not in instance.__dict__:
                instance.__dict__[self.name] = self.get_relation()
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

    def traverse_field(self, path: str) -> Tuple[Any, str, str]:
        return self.foreign_key.reverse_traverse_field(path)

    def get_relation(self, **kwargs: Any) -> ManyRelationProtocol:
        return self.foreign_key.get_relation(**kwargs)

    def is_cross_db(self) -> bool:
        return self.foreign_key.is_cross_db()

    def clean(self, name: str, value: Any, for_query: bool = False) -> Dict[str, Any]:
        if not for_query:
            return {}
        return self.related_to.meta.pk.clean("pk", value, for_query=for_query)  # type: ignore

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self}>"

    def __str__(self) -> str:
        return f"({self.related_to.__name__}={self.related_name})"
