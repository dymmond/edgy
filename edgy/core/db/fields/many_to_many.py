from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Literal,
    Optional,
    Sequence,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
)

from edgy.core.db.constants import CASCADE
from edgy.core.db.fields.base import BaseField, BaseForeignKey
from edgy.core.db.fields.factories import ForeignKeyFieldFactory
from edgy.core.db.fields.foreign_keys import ForeignKey
from edgy.core.db.relationships.relation import ManyRelation
from edgy.core.terminal import Print
from edgy.core.utils.models import create_edgy_model
from edgy.protocols.many_relationship import ManyRelationProtocol

if TYPE_CHECKING:

    from edgy import Model

T = TypeVar("T", bound="Model")


terminal = Print()


class BaseManyToManyForeignKeyField(BaseForeignKey):
    is_m2m: bool = True
    def __init__(
        self,
        *,
        to_fields: Sequence[str] = (),
        to_foreign_key: str = "",
        from_fields: Sequence[str] = (),
        from_foreign_key: str = "",
        through: Union[str, Type["Model"]] = "",
        embed_through: str="",
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.to_fields = to_fields
        self.to_foreign_key = to_foreign_key
        self.from_fields = from_fields
        self.from_foreign_key = from_foreign_key
        self.through = through
        self.embed_through = embed_through

    def get_relation(self, **kwargs: Any) -> ManyRelationProtocol:
        return ManyRelation(through=self.through, to=self.to, from_foreign_key=self.from_foreign_key, to_foreign_key=self.to_foreign_key, embed_through=self.embed_through, **kwargs)

    def get_inverse_relation(self, **kwargs: Any) -> ManyRelationProtocol:
        return ManyRelation(through=self.through, to=self.owner, from_foreign_key=self.to_foreign_key, to_foreign_key=self.from_foreign_key, embed_through=self.embed_through, **kwargs)


    def add_model_to_register(self, model: Any) -> None:
        """
        Adds the model to the registry to make sure it can be generated by the Migrations
        """
        self.registry.models[model.__name__] = model

    def create_through_model(self) -> None:
        """
        Creates the default empty through model.

        Generates a middle model based on the owner of the field and the field itself and adds
        it to the main registry to make sure it generates the proper models and migrations.
        """
        from edgy.core.db.models.metaclasses import MetaInfo

        self.to = self.target
        __bases__: Tuple[Type["Model"], ...] = ()

        if self.through:
            if isinstance(self.through, str):
                self.through = self.registry.models[self.through]
            through = cast(Type["Model"], self.through)
            if through.meta.abstract:
                __bases__ = (through,)
            else:
                if not self.from_foreign_key:
                    candidate = None
                    for field_name, field in through.meta.foreign_key_fields.items():
                        if field.target == self.owner:
                            if candidate:
                                raise ValueError("multiple foreign keys to owner")
                            else:
                                candidate = field_name
                    if not candidate:
                        raise ValueError("no foreign key fo owner found")
                    self.from_foreign_key = candidate
                if not self.to_foreign_key:
                    candidate = None
                    for field_name, field in through.meta.foreign_key_fields.items():
                        if field.target == self.to:
                            if candidate:
                                raise ValueError("multiple foreign keys to target")
                            else:
                                candidate = field_name
                    if not candidate:
                        raise ValueError("no foreign key fo target found")
                    self.to_foreign_key = candidate
                return
        owner_name = self.owner.__name__
        to_name = self.to.__name__
        class_name = f"{owner_name}{to_name}"
        if not self.from_foreign_key:
            self.from_foreign_key = owner_name.lower()

        if not self.to_foreign_key:
            self.to_foreign_key = to_name.lower()

        tablename = f"{owner_name.lower()}s_{to_name}s".lower()

        new_meta: MetaInfo = MetaInfo(None, tablename=tablename, registry=self.registry, multi_related=[to_name.lower()])

        to_related_name: Union[str, Literal[False]]
        if self.related_name is False:
            to_related_name = False
        elif self.related_name:
            to_related_name = f"{self.related_name}"
        else:
            to_related_name = f"{to_name.lower()}_{class_name.lower()}s_set"

        fields = {
            f"{self.from_foreign_key}": ForeignKey(
                self.owner,
                null=True,
                on_delete=CASCADE,
                related_name=False,
                related_fields=self.from_fields,
                primary_key=True
            ),
            f"{self.to_foreign_key}": ForeignKey(
                self.to,
                null=True,
                on_delete=CASCADE,
                related_name=to_related_name,
                related_fields=self.to_fields,
                embed_parent=(self.from_foreign_key, self.embed_through),
                primary_key=True,
                relation_fn=self.get_inverse_relation
            ),
        }

        # Create the through model
        through_model = create_edgy_model(
            __name__=class_name,
            __module__=self.__module__,
            __definitions__=fields,
            __metadata__=new_meta,
            __bases__=__bases__
        )
        self.through = through_model
        self.add_model_to_register(self.through)

    def to_model(self, field_name: str, value: Any, phase: str = "") -> Dict[str, Any]:
        """
        Meta field
        """
        if isinstance(value, ManyRelationProtocol):
            return {field_name: value}
        return {field_name: self.get_relation(refs=value)}

    def has_default(self) -> bool:
        """Checks if the field has a default value set"""
        return False

    def get_default_values(self, field_name: str, cleaned_data: Dict[str, Any]) -> Any:
        """
        Meta field
        """
        return {}

    def __get__(self, instance: "Model", owner: Any = None) -> ManyRelation:
        if instance:
            if self.name not in instance.__dict__:
                instance.__dict__[self.name] = self.get_relation()
            if instance.__dict__[self.name].instance is None:
                instance.__dict__[self.name].instance = instance
            return instance.__dict__[self.name]  # type: ignore
        raise ValueError("Missing instance")

    def __set__(self, instance: "Model", value: Any) -> None:
        relation = self.__get__(instance)
        if not isinstance(value, Sequence):
            value = [value]
        for v in value:
            relation._add_object(v)


class ManyToManyField(ForeignKeyFieldFactory):
    _type: Any = Any
    _bases = (BaseManyToManyForeignKeyField,)

    def __new__(  # type: ignore
        cls,
        to: Union["Model", str],
        *,
        through: Optional["Model"] = None,
        from_fields: Sequence[str] = (),
        to_fields: Sequence[str] = (),
        **kwargs: Any,
    ) -> BaseField:
        for argument in ["null", "on_delete", "on_update"]:
            if kwargs.get(argument, None):
                terminal.write_warning(f"Declaring `{argument}` on a ManyToMany relationship has no effect.")
        kwargs["null"] = True
        kwargs["on_delete"] = CASCADE
        kwargs["on_update"] = CASCADE

        return super().__new__(cls, to=to, through=through, **kwargs)

ManyToMany = ManyToManyField
