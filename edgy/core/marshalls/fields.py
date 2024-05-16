from typing import Any, ClassVar, Union, Unpack

from pydantic._internal import _repr
from pydantic.fields import FieldInfo, _FieldInfoInputs

from edgy.types import Undefined


class BaseMarshallField(FieldInfo, _repr.Representation):
    __is_method__: ClassVar[bool] = False

    def __init__(
        self,
        field_type: type,
        source: Union[str, None] = None,
        allow_null: bool = False,
        default: Any = Undefined,
        **kwargs: Unpack[_FieldInfoInputs],
    ) -> None:
        self.source = source
        self.null = allow_null
        self.field_type = field_type
        super().__init__(**kwargs)

        if self.null and default is Undefined:
            self.default = None
        if default is not Undefined:
            self.default = default

    def is_required(self) -> bool:
        """Check if the argument is required.

        Returns:
            `True` if the argument is required, `False` otherwise.
        """
        return False if self.null else True


class MarshallMethodField(BaseMarshallField):
    """
    The base field for the function marshall.
    """

    __is_method__: ClassVar[bool] = True


class MarshallField(BaseMarshallField):
    def __init__(
        self,
        field_type: type,
        source: Union[str, None] = None,
        **kwargs: _FieldInfoInputs,
    ) -> None:
        super().__init__(field_type, source, allow_null=True, default=None, **kwargs)
