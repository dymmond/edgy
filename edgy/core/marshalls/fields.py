from typing import Any, ClassVar, Union

from pydantic.fields import FieldInfo

from edgy.types import Undefined


class BaseMarshallField(FieldInfo):
    __is_method__: ClassVar[bool] = False

    def __init__(
        self,
        field_type: type,
        source: Union[str, None] = None,
        allow_null: bool = False,
        default: Any = Undefined,
        **kwargs: Any,
    ) -> None:
        self.source = source
        self.null = allow_null
        self.field_type = field_type
        super().__init__(**kwargs)

        if default is not Undefined:
            self.default = default
        elif self.null:
            self.default = None

    def is_required(self) -> bool:
        """Check if the argument is required.

        Returns:
            `True` if the argument is required, `False` otherwise.
        """
        return not self.null


class MarshallMethodField(BaseMarshallField):
    """
    The base field for the function marshall.
    """

    __is_method__: ClassVar[bool] = True

    def __init__(
        self,
        field_type: type,
        **kwargs: dict[str, Any],
    ) -> None:
        kwargs.pop("default", None)
        kwargs.pop("source", None)
        kwargs.pop("allow_null", None)
        super().__init__(field_type, source=None, allow_null=True, default=None, **kwargs)


class MarshallField(BaseMarshallField):
    def __init__(
        self,
        field_type: type,
        source: Union[str, None] = None,
        **kwargs: dict[str, Any],
    ) -> None:
        kwargs.pop("default", None)
        kwargs.pop("allow_null", None)
        super().__init__(field_type, source, allow_null=True, default=None, **kwargs)
