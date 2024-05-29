from typing import Any, ClassVar, List, Optional, Sequence

from pydantic import model_validator
from pydantic.dataclasses import dataclass


@dataclass
class Index:
    """
    Class responsible for handling and declaring the database indexes.
    """

    suffix: str = "idx"
    __max_name_length__: ClassVar[int] = 63
    name: Optional[str] = None
    fields: Optional[Sequence[str]] = None

    @model_validator(mode="before")
    def validate_data(cls, values: Any) -> Any:
        name = values.kwargs.get("name")

        if name is not None and len(name) > cls.__max_name_length__:
            raise ValueError(f"The max length of the index name must be {cls.__max_name_length__}. Got {len(name)}")

        fields = values.kwargs.get("fields")
        if not isinstance(fields, (tuple, list)):
            raise ValueError("Index.fields must be a list or a tuple.")

        if fields and not all(isinstance(field, str) for field in fields):
            raise ValueError("Index.fields must contain only strings with field names.")

        if name is None:
            suffix = values.kwargs.get("suffix", cls.suffix)
            values.kwargs["name"] = f"{suffix}_{'_'.join(fields)}"
        return values


@dataclass
class UniqueConstraint:
    """
    Class responsible for handling and declaring the database unique_together.
    """

    fields: List[str]
    name: Optional[str] = None
    __max_name_length__: ClassVar[int] = 63

    @model_validator(mode="before")
    def validate_data(cls, values: Any) -> Any:
        name = values.kwargs.get("name")

        if name is not None and len(name) > cls.__max_name_length__:
            raise ValueError(
                f"The max length of the constraint name must be {cls.__max_name_length__}. Got {len(name)}"
            )

        fields = values.kwargs.get("fields")
        if not isinstance(fields, (tuple, list)):
            raise ValueError("UniqueConstraint.fields must be a list or a tuple.")

        if fields and not all(isinstance(field, str) for field in fields):
            raise ValueError("UniqueConstraint.fields must contain only strings with field names.")

        return values
