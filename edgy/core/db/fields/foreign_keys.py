from typing import TYPE_CHECKING, Any, Optional, Type, Union, cast

import sqlalchemy

import edgy
from edgy.core.connection.registry import Registry
from edgy.core.db.base import BaseField
from edgy.core.db.constants import CASCADE, RESTRICT, SET_NULL
from edgy.core.terminal import Print
from edgy.exceptions import FieldDefinitionError

if TYPE_CHECKING:
    from edgy import Model

CLASS_DEFAULTS = ["cls", "__class__", "kwargs"]
terminal = Print()


class ForeignKeyFieldFactory:
    """The base for all model fields to be used with Edgy"""

    _bases = (BaseField,)
    _type: Any = None

    def __new__(cls, *args: Any, **kwargs: Any) -> BaseField:  # type: ignore
        cls.validate(**kwargs)

        to: Any = kwargs.pop("to", None)
        null: bool = kwargs.pop("null", False)
        on_update: str = kwargs.pop("on_update", CASCADE)
        on_delete: str = kwargs.pop("on_delete", RESTRICT)
        related_name: str = kwargs.pop("related_name", None)
        comment: str = kwargs.pop("comment", None)
        through: Any = kwargs.pop("through", None)
        owner: Any = kwargs.pop("owner", None)
        server_default: Any = kwargs.pop("server_default", None)
        server_onupdate: Any = kwargs.pop("server_onupdate", None)
        registry: Registry = kwargs.pop("registry", None)
        field_type = cls._type

        namespace = dict(
            __type__=field_type,
            to=to,
            on_update=on_update,
            on_delete=on_delete,
            related_name=related_name,
            annotation=field_type,
            null=null,
            comment=comment,
            owner=owner,
            server_default=server_default,
            server_onupdate=server_onupdate,
            through=through,
            registry=registry,
            **kwargs,
        )
        Field = type(cls.__name__, cls._bases, {})
        return Field(**namespace)  # type: ignore

    @classmethod
    def validate(cls, **kwargs: Any) -> None:  # pragma no cover
        """
        Used to validate if all required parameters on a given field type are set.
        :param kwargs: all params passed during construction
        :type kwargs: Any
        """

    @classmethod
    def get_column_type(cls, **kwargs: Any) -> Any:
        """Returns the propery column type for the field"""
        return None


class ForeignKey(ForeignKeyFieldFactory):
    _type = Any

    def __new__(  # type: ignore
        cls,
        *,
        to: "Model",
        null: bool = False,
        on_update: Optional[str] = CASCADE,
        on_delete: Optional[str] = RESTRICT,
        related_name: Optional[str] = None,
        **kwargs: Any,
    ) -> BaseField:
        kwargs = {
            **kwargs,
            **{key: value for key, value in locals().items() if key not in CLASS_DEFAULTS},
        }

        return super().__new__(cls, **kwargs)

    @classmethod
    def validate(cls, **kwargs: Any) -> None:
        on_delete = kwargs.get("on_delete", None)
        on_update = kwargs.get("on_update", None)
        null = kwargs.get("null")

        if on_delete is None:
            raise FieldDefinitionError("on_delete must not be null")

        if on_delete == SET_NULL and not null:
            raise FieldDefinitionError("When SET_NULL is enabled, null must be True.")

        if on_update and (on_update == SET_NULL and not null):
            raise FieldDefinitionError("When SET_NULL is enabled, null must be True.")

    @property
    def target(self) -> Any:
        """
        The target of the ForeignKey model.
        """
        if not hasattr(self, "_target"):
            if isinstance(self.to, str):
                self._target = self.registry.models[self.to]  # type: ignore
            else:
                self._target = self.to
        return self._target

    def get_column(self, name: str) -> Any:
        target = self.target
        to_field = target.fields[target.pkname]

        column_type = to_field.get_column_type()
        constraints = [
            sqlalchemy.schema.ForeignKey(
                f"{target._meta.tablename}.{target.pkname}",
                ondelete=self.on_delete,
                onupdate=self.on_update,
                name=f"fk_{self.owner._meta.tablename}_{target._meta.tablename}"
                f"_{target.pkname}_{name}",
            )
        ]
        return sqlalchemy.Column(name, column_type, *constraints, nullable=self.null)

    def get_related_name(self) -> str:
        """
        Returns the name of the related name of the current relationship between the to and target.

        :return: Name of the related_name attribute field.
        """
        return self.related_name

    def expand_relationship(self, value: Any) -> Any:
        target = self.target
        if isinstance(value, target):
            return value
        return target(pk=value)


class OneToOneField(ForeignKey):
    """
    Representation of a one to one field.
    """

    def get_column(self, name: str) -> sqlalchemy.Column:
        target = self.target
        to_field = target.fields[target.pkname]

        column_type = to_field.get_column_type()
        constraints = [
            sqlalchemy.schema.ForeignKey(
                f"{target._meta.tablename}.{target.pkname}", ondelete=self.on_delete
            )
        ]
        return sqlalchemy.Column(
            name,
            column_type,
            *constraints,
            nullable=self.null,
            unique=True,
        )


OneToOne = OneToOneField


class ManyToManyField(ForeignKeyFieldFactory):
    _type = Any

    def __new__(  # type: ignore
        cls,
        *,
        to: "Model",
        through: Optional["Model"] = None,
        **kwargs: Any,
    ) -> BaseField:
        kwargs = {
            **kwargs,
            **{key: value for key, value in locals().items() if key not in CLASS_DEFAULTS},
        }

        return super().__new__(cls, **kwargs)

    @property
    def target(self) -> Any:
        if not hasattr(self, "_target"):
            if isinstance(self.to, str):
                self._target = self.registry.models[self.to]  # type: ignore
            else:
                self._target = self.to
        return self._target

    def get_column(self, name: str) -> sqlalchemy.Column:
        target = self.target
        to_field = target.fields[target.pkname]

        column_type = to_field.get_column_type()
        constraints = [
            sqlalchemy.schema.ForeignKey(
                f"{target._meta.tablename}.{target.pkname}",
                ondelete=CASCADE,
                onupdate=CASCADE,
                name=f"fk_{self.owner._meta.tablename}_{target._meta.tablename}"
                f"_{target.pkname}_{name}",
            )
        ]
        return sqlalchemy.Column(name, column_type, *constraints, nullable=self.null)

    @classmethod
    def validate(cls, **kwargs: Any) -> None:
        related_name = kwargs.get("related_name", None)

        if "null" in kwargs:
            terminal.write_warning("Declaring `null` on a ManyToMany relationship has no effect.")

        if related_name:
            assert isinstance(related_name, str), "related_name must be a string."

        kwargs["related_name"] = related_name.lower() if related_name else None

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
        if self.through:  # type: ignore
            if isinstance(self.through, str):  # type: ignore
                self.through = self.owner._meta.registry.models[self.through]  # type: ignore

            self.through._meta.is_multi = True
            self.through._meta.multi_related = [self.to.__name__.lower()]  # type: ignore
            return self.through

        owner_name = self.owner.__name__
        to_name = self.to.__name__
        class_name = f"{owner_name}{to_name}"
        tablename = f"{owner_name.lower()}s_{to_name}s".lower()

        new_meta_namespace = {
            "tablename": tablename,
            "registry": self.owner._meta.registry,
            "is_multi": True,
            "multi_related": [to_name.lower()],
        }

        new_meta = type("MetaInfo", (), new_meta_namespace)

        # Define the related names
        owner_related_name = (
            f"{self.related_name}_{class_name.lower()}s_set"
            if self.related_name
            else f"{owner_name.lower()}_{class_name.lower()}s_set"
        )

        to_related_name = (
            f"{self.related_name}"
            if self.related_name
            else f"{to_name.lower()}_{class_name.lower()}s_set"
        )

        through_model = type(
            class_name,
            (edgy.Model,),
            {
                "Meta": new_meta,
                "id": edgy.IntegerField(primary_key=True),
                f"{owner_name.lower()}": ForeignKey(  # type: ignore
                    self.owner,
                    null=True,
                    on_delete=CASCADE,
                    related_name=owner_related_name,
                ),
                f"{to_name.lower()}": ForeignKey(  # type: ignore
                    self.to, null=True, on_delete=CASCADE, related_name=to_related_name
                ),
            },
        )
        self.through = cast(Type["Model"], through_model)

        self.add_model_to_register(self.through)


ManyToMany = ManyToManyField
