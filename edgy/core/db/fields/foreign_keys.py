from typing import TYPE_CHECKING, Any, Optional, TypeVar

import sqlalchemy

from edgy.core.connection.registry import Registry
from edgy.core.db.constants import CASCADE, RESTRICT, SET_NULL
from edgy.core.db.fields._base_fk import BaseField, BaseForeignKey
from edgy.core.terminal import Print
from edgy.exceptions import FieldDefinitionError

if TYPE_CHECKING:
    from edgy import Model

T = TypeVar("T", bound="Model")


CLASS_DEFAULTS = ["cls", "__class__", "kwargs"]
terminal = Print()


class ForeignKeyFieldFactory:
    """The base for all model fields to be used with Edgy"""

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
        secret: bool = kwargs.pop("secret", False)
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
            column_type=field_type,
            secret=secret,
            constraints=cls.get_constraints(),
            **kwargs,
        )
        Field = type(cls.__name__, (BaseForeignKeyField, BaseField), {})
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

    @classmethod
    def get_constraints(cls, **kwargs: Any) -> Any:
        return []


class BaseForeignKeyField(BaseForeignKey):
    def get_column(self, name: str) -> Any:
        target = self.target
        to_field = target.fields[target.pkname]

        column_type = to_field.column_type
        constraints = [
            sqlalchemy.schema.ForeignKey(
                f"{target.meta.tablename}.{target.pkname}",
                ondelete=self.on_delete,
                onupdate=self.on_update,
                name=f"fk_{self.owner.meta.tablename}_{target.meta.tablename}"
                f"_{target.pkname}_{name}",
            )
        ]
        return sqlalchemy.Column(name, column_type, *constraints, nullable=self.null)


class ForeignKey(ForeignKeyFieldFactory):
    _type: Any = Any

    def __new__(  # type: ignore
        cls,
        to: "Model",
        *,
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
