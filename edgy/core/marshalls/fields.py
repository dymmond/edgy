from typing import Any, ClassVar

from pydantic.fields import FieldInfo

from edgy.types import Undefined


class BaseMarshallField(FieldInfo):
    """
    Base class for defining fields within Edgy Marshalls.
    It extends Pydantic's `FieldInfo` to add specific functionalities
    required for Marshall fields, such as `source` mapping and
    `null` allowance.

    Attributes:
        __is_method__ (ClassVar[bool]): A class variable indicating if this field
                                        is a method-based field (i.e., its value
                                        is derived from a getter method). Defaults to False.
    """

    __is_method__: ClassVar[bool] = False

    def __init__(
        self,
        field_type: type,
        source: str | None = None,
        allow_null: bool = False,
        default: Any = Undefined,
        **kwargs: Any,
    ) -> None:
        """
        Initializes a BaseMarshallField.

        Args:
            field_type (type): The Python type of the field (e.g., `str`, `int`, `list`).
            source (str | None): The name of the attribute on the original Edgy model
                                 from which this marshall field's value should be sourced.
                                 If None, the marshall field's name is used as the source.
            allow_null (bool): If True, the field can be None. If False, it's considered required.
                               Defaults to False.
            default (Any): The default value for the field. If not provided and `allow_null` is True,
                           the default will implicitly be None. Uses `Undefined` as a sentinel.
            **kwargs (Any): Additional keyword arguments passed directly to Pydantic's `FieldInfo`
                            constructor (e.g., `description`, `alias`, `title`).
        """
        self.source = source
        self.null = allow_null  # Stores whether null values are allowed
        self.field_type = field_type  # Stores the Python type of the field

        # Call the parent Pydantic FieldInfo constructor.
        super().__init__(**kwargs)

        # Set the default value based on `default` and `allow_null`.
        if default is not Undefined:
            self.default = default
        elif self.null:
            self.default = None  # If null is allowed and no default is given, default to None.

    def is_required(self) -> bool:
        """
        Checks if the marshall field is considered required.

        Returns:
            bool: `True` if the field does not allow null values, `False` otherwise.
        """
        return not self.null


class MarshallMethodField(BaseMarshallField):
    """
    A specialized `BaseMarshallField` for fields whose values are derived from
    methods on the Marshall class itself (e.g., `get_full_name`).

    These fields are inherently read-only and typically do not have a direct
    `source` from the model or a default value other than None (as they are
    computed).
    """

    __is_method__: ClassVar[bool] = True  # Mark this as a method-based field.

    def __init__(
        self,
        field_type: type,
        **kwargs: dict[str, Any],
    ) -> None:
        """
        Initializes a MarshallMethodField.

        Args:
            field_type (type): The Python type of the value returned by the getter method.
            **kwargs (dict[str, Any]): Additional keyword arguments for `FieldInfo`.
                                      `default`, `source`, and `allow_null` are
                                      explicitly popped as they are managed internally
                                      for method fields.
        """
        # Remove parameters that are implicitly handled by method fields.
        kwargs.pop("default", None)
        kwargs.pop("source", None)
        kwargs.pop("allow_null", None)

        # Call the parent constructor with fixed values for method fields.
        # Method fields are always `allow_null=True` and `default=None`
        # as their value is dynamically computed.
        super().__init__(field_type, source=None, allow_null=True, default=None, **kwargs)


class MarshallField(BaseMarshallField):
    """
    A concrete `BaseMarshallField` for standard marshall fields that map directly
    to model attributes or have a simple source.

    By default, it allows null values and sets the default to None, making them
    optional unless explicitly configured otherwise via `allow_null=False` (though
    this specific class overrides the defaults from `BaseMarshallField`).
    """

    def __init__(
        self,
        field_type: type,
        source: str | None = None,
        **kwargs: dict[str, Any],
    ) -> None:
        """
        Initializes a MarshallField.

        Args:
            field_type (type): The Python type of the field.
            source (str | None): The name of the attribute on the original Edgy model
                                 from which this marshall field's value should be sourced.
                                 If None, the marshall field's name is used as the source.
            **kwargs (dict[str, Any]): Additional keyword arguments for `FieldInfo`.
                                      `default` and `allow_null` are explicitly popped
                                      as this class sets them to `None` and `True` respectively.
        """
        # Remove parameters that are implicitly handled by this field type.
        kwargs.pop("default", None)
        kwargs.pop("allow_null", None)

        # Call the parent constructor, explicitly setting allow_null=True and default=None.
        # This makes MarshallField behave as an optional field by default.
        super().__init__(field_type, source, allow_null=True, default=None, **kwargs)
