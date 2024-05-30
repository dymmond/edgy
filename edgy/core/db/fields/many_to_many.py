from typing import TYPE_CHECKING, Any, Optional, Sequence, TypeVar, Union

import sqlalchemy

import edgy
from edgy.core.db.constants import CASCADE
from edgy.core.db.fields.base import BaseField, BaseForeignKey
from edgy.core.db.fields.core import ForeignKeyFieldFactory
from edgy.core.db.fields.foreign_keys import ForeignKey
from edgy.core.terminal import Print
from edgy.core.utils.models import create_edgy_model

if TYPE_CHECKING:
    from edgy import Model

T = TypeVar("T", bound="Model")


CLASS_DEFAULTS = ["cls", "__class__", "kwargs"]
CHAR_LIMIT = 63
terminal = Print()


class BaseManyToManyForeignKeyField(BaseForeignKey):
    is_m2m: bool = True

    def add_model_to_register(self, model: Any) -> None:
        """
        Adds the model to the registry to make sure it can be generated by the Migrations
        """
        self.registry.models[model.__name__] = model

    def create_through_model(self) -> Any:
        """
        Creates the default empty through model.

        Generates a middle model based on the owner of the field and the field itself and adds
        it to the main registry to make sure it generates the proper models and migrations.
        """
        from edgy.core.db.models.metaclasses import MetaInfo

        self.to = self.target

        if self.through:
            if isinstance(self.through, str):
                self.through = self.owner.meta.registry.models[self.through]

            self.through.meta.is_multi = True
            self.through.meta.multi_related = [self.to.__name__.lower()]
            return self.through

        owner_name = self.owner.__name__
        to_name = self.to.__name__
        class_name = f"{owner_name}{to_name}"
        tablename = f"{owner_name.lower()}s_{to_name}s".lower()

        new_meta_namespace = {
            "tablename": tablename,
            "registry": self.registry,
            "is_multi": True,
            "multi_related": [to_name.lower()],
        }

        new_meta: MetaInfo = MetaInfo(None)
        new_meta.load_dict(new_meta_namespace)

        # Define the related names
        owner_related_name = (
            f"{self.related_name}_{class_name.lower()}s_set"
            if self.related_name
            else f"{owner_name.lower()}_{class_name.lower()}s_set"
        )

        to_related_name = (
            f"{self.related_name}" if self.related_name else f"{to_name.lower()}_{class_name.lower()}s_set"
        )
        fields = {
            "id": edgy.IntegerField(primary_key=True),
            f"{owner_name.lower()}": ForeignKey(
                self.owner,
                null=True,
                on_delete=CASCADE,
                related_name=owner_related_name,
            ),
            f"{to_name.lower()}": ForeignKey(self.to, null=True, on_delete=CASCADE, related_name=to_related_name),
        }

        # Create the through model
        through_model = create_edgy_model(
            __name__=class_name,
            __module__=self.__module__,
            __definitions__=fields,
            __metadata__=new_meta,
        )
        self.through = through_model
        self.add_model_to_register(self.through)

    def get_fk_name(self, name: str) -> str:
        """
        Builds the fk name for the engine.

        Engines have a limitation of the foreign key being bigger than 63
        characters.

        if that happens, we need to assure it is small.
        """
        fk_name = f"fk_{self.owner.meta.tablename}_{self.target.meta.tablename}_{self.target.pknames[0]}_{name}"
        if not len(fk_name) > CHAR_LIMIT:
            return fk_name
        return fk_name[:CHAR_LIMIT]

    def get_columns(self, name: str) -> Sequence[sqlalchemy.Column]:
        """
        Builds the column for the target.
        """
        target = self.target
        to_field = target.fields[target.pknames[0]]

        column_type = to_field.column_type
        constraints = [
            sqlalchemy.schema.ForeignKey(
                f"{target.meta.tablename}.{target.pknames[0]}",
                ondelete=CASCADE,
                onupdate=CASCADE,
                name=self.get_fk_name(name=name),
            )
        ]
        return [sqlalchemy.Column(name, column_type, *constraints, nullable=self.null)]

    def has_default(self) -> bool:
        """Checks if the field has a default value set"""
        return hasattr(self, "default")

    def expand_relationship(self, value: Any) -> Any:
        return value


class ManyToManyField(ForeignKeyFieldFactory):
    _type: Any = Any
    _bases = (BaseManyToManyForeignKeyField,)

    def __new__(  # type: ignore
        cls,
        to: Union["Model", str],
        *,
        through: Optional["Model"] = None,
        **kwargs: Any,
    ) -> BaseField:
        null = kwargs.get("null", None)
        if null:
            terminal.write_warning("Declaring `null` on a ManyToMany relationship has no effect.")

        kwargs = {
            **kwargs,
            **{key: value for key, value in locals().items() if key not in CLASS_DEFAULTS},
        }
        kwargs["null"] = True
        return super().__new__(cls, **kwargs)

    @classmethod
    def validate(cls, **kwargs: Any) -> None:
        related_name = kwargs.get("related_name", None)

        if related_name:
            assert isinstance(related_name, str), "related_name must be a string."

        kwargs["related_name"] = related_name.lower() if related_name else None


ManyToMany = ManyToManyField
