from typing import Any

from pydantic.fields import FieldInfo

from edgy.types import Undefined


class Constraint(FieldInfo):
    """
    The base field for all Edgy data model fields.
    """

    def __init__(
        self,
        **kwargs: Any,
    ) -> None:
        self.name: str = kwargs.pop("name", None)
        exclusive = kwargs.pop("exclusive", False)
        self.expression = kwargs.pop("expression", None)
        self.one_of = kwargs.pop("one_of", None)
        self.max_value = kwargs.pop("max_value", None)
        self.max_exclusive_value = kwargs.pop("max_exclusive_value", None)
        self.max_length = kwargs.pop("max_length", None)
        self.min_value = kwargs.pop("min_value", None)
        self.min_exclusive_value = kwargs.pop("min_exclusive_value", None)
        self.min_length = kwargs.pop("min_length", None)
        self.regexp: str = kwargs.pop("regexp", None)

        for name, value in kwargs.items():
            setattr(self, name, value)

        super().__init__(
            default=Undefined,
            alias=self.name,
            required=exclusive,
            regex=self.regexp,
            **kwargs,
        )

    def get_alias(self) -> str:
        """
        Used to translate the model column names into database column tables.
        """
        return self.name
