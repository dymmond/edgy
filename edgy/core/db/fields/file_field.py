import copy
import datetime
import decimal
import enum
import ipaddress
import re
import uuid
from enum import EnumMeta
from typing import Any, Optional, Pattern, Sequence, Set, Tuple, Union

import pydantic
import sqlalchemy
from pydantic import EmailStr

from edgy.core.db.fields._internal import IPAddress
from edgy.core.db.fields._validators import IPV4_REGEX, IPV6_REGEX
from edgy.core.db.fields.base import BaseField
from edgy.exceptions import FieldDefinitionError

CLASS_DEFAULTS = ["cls", "__class__", "kwargs"]


class Field:
    def check(self, value: Any) -> Any:
        """
        Runs the checks for the fields being validated.
        """
        return value


class FieldFactory:
    """The base for all model fields to be used with Edgy"""

    _bases = (
        Field,
        BaseField,
    )
    _type: Any = None

    def __new__(cls, *args: Any, **kwargs: Any) -> BaseField:  # type: ignore
        cls.validate(**kwargs)
        arguments = copy.deepcopy(kwargs)

        null: bool = kwargs.pop("null", False)
        name: str = kwargs.pop("name", None)
        comment: str = kwargs.pop("comment", None)
        owner = kwargs.pop("owner", None)
        secret: bool = kwargs.pop("secret", False)
        field_type = cls._type

        namespace = dict(
            __type__=field_type,
            annotation=field_type,
            name=name,
            null=null,
            comment=comment,
            owner=owner,
            format=format,
            column_type=cls.get_column_type(**arguments),
            constraints=cls.get_constraints(),
            secret=secret,
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

    @classmethod
    def get_constraints(cls, **kwargs: Any) -> Any:
        return []


class FileField(FieldFactory):
    _type: Any

    def __new__(  # type: ignore
        cls,
        verbose_name: Union[str, None] = None,
        name: Union[str, None] = None,
        storage: Union[str, None] = None,
        **kwargs: Any,
    ) -> BaseField:
        kwargs = {
            **kwargs,
            **{key: value for key, value in locals().items() if key not in CLASS_DEFAULTS},
        }

        return super().__new__(cls, **kwargs)

    @classmethod
    def get_column_type(cls, **kwargs: Any) -> Any:
        return sqlalchemy.Text()
