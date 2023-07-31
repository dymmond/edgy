import decimal
from typing import Any, Optional, Pattern, Sequence, Union

import sqlalchemy
from pydantic.fields import FieldInfo

from edgy.core.connection.registry import Registry
from edgy.types import Undefined


class BaseField(FieldInfo):
    """
    The base field for all Edgy data model fields.
    """

    def __init__(
        self,
        *,
        default: Any = Undefined,
        title: Optional[str] = None,
        description: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        self.null: bool = kwargs.pop("null", False)
        if self.null and default is Undefined:
            default = None
        if default is not Undefined:
            self.default = default

        self.title = title
        self.description = description
        self.read_only: str = kwargs.pop("read_only", False)
        self.help_text: str = kwargs.pop("help_text", None)
        self.blank: bool = kwargs.pop("blank", False)
        self.pattern: Pattern = kwargs.pop("pattern", None)
        self.autoincrement: bool = kwargs.pop("autoincrement", False)
        self.primary_key: bool = kwargs.pop("primary_key", False)
        self.related_name: str = kwargs.pop("related_name", None)
        self.unique: bool = kwargs.pop("unique", False)
        self.index: bool = kwargs.pop("index", False)
        self.choices: Sequence = kwargs.pop("choices", None)
        self.owner: Any = kwargs.pop("owner", None)
        self.name: str = kwargs.pop("name", None)
        self.alias: str = kwargs.pop("name", None)
        self.max_digits: str = kwargs.pop("max_digits", None)
        self.decimal_places: str = kwargs.pop("decimal_places", None)
        self.regex: str = kwargs.pop("regex", None)
        self.min_length: Optional[Union[int, float, decimal.Decimal]] = kwargs.pop(
            "min_length", None
        )
        self.max_length: Optional[Union[int, float, decimal.Decimal]] = kwargs.pop(
            "max_length", None
        )
        self.minimum: Optional[Union[int, float, decimal.Decimal]] = kwargs.pop("minimum", None)
        self.maximum: Optional[Union[int, float, decimal.Decimal]] = kwargs.pop("maximum", None)
        self.exclusive_mininum: Optional[Union[int, float, decimal.Decimal]] = kwargs.pop(
            "exclusive_mininum", None
        )
        self.exclusive_maximum: Optional[Union[int, float, decimal.Decimal]] = kwargs.pop(
            "exclusive_maximum", None
        )
        self.multiple_of: Optional[Union[int, float, decimal.Decimal]] = kwargs.pop(
            "multiple_of", None
        )
        self.through: Any = kwargs.pop("through", None)
        self.server_default: Any = kwargs.pop("server_default", None)
        self.server_onupdate: Any = kwargs.pop("server_onupdate", None)
        self.registry: Registry = kwargs.pop("registry", None)
        self.comment = kwargs.get("comment", None)

        for name, value in kwargs.items():
            setattr(self, name, value)

        super().__init__(
            default=default,
            alias=self.alias,
            title=title,
            description=description,
            min_length=self.min_length,
            max_length=self.max_length,
            ge=self.minimum,
            le=self.maximum,
            gt=self.exclusive_mininum,
            lt=self.exclusive_maximum,
            multiple_of=self.multiple_of,
            max_digits=self.max_digits,
            decimal_places=self.decimal_places,
            pattern=self.regex,
            **kwargs,
        )

    def is_required(self) -> bool:
        """Check if the argument is required.

        Returns:
            `True` if the argument is required, `False` otherwise.
        """
        required = False if self.null else True
        return required

    def get_alias(self) -> str:
        """
        Used to translate the model column names into database column tables.
        """
        return self.name

    def is_primary_key(self) -> bool:
        """
        Sets the autoincrement to True if the field is primary key.
        """
        if self.primary_key:
            self.autoincrement = True
        return False

    def has_default(self) -> bool:
        """Checks if the field has a default value set"""
        return bool(self.default is not None and self.default is not Undefined)

    def get_column(self, name: str) -> Any:
        """
        Returns the column type of the field being declared.
        """
        column_type = self.get_column_type()
        constraints = self.get_constraints()
        column = sqlalchemy.Column(
            name,
            column_type,
            *constraints,
            primary_key=self.primary_key,
            nullable=self.null and not self.primary_key,
            index=self.index,
            unique=self.unique,
            default=self.default,
            comment=self.comment,
            server_default=self.server_default,
            server_onupdate=self.server_onupdate,
        )

    def expand_relationship(self, value: Any, child: Any, to_register: bool = True) -> Any:
        """
        Used to be overritten by any Link class.
        """

        return value

    def get_related_name(self) -> str:
        """Returns the related name used for reverse relations"""
        return ""

    def get_constraints(self) -> Any:
        return []
