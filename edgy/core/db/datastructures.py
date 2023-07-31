from typing import Any, List, Optional, Sequence

from pydantic import model_validator
from pydantic.dataclasses import dataclass


@dataclass
class Index:
    """
    Class responsible for handling and declaring the database indexes.
    """

    suffix: str = "idx"
    max_name_length: int = 30
    name: Optional[str] = None
    fields: Optional[Sequence[str]] = None

    @model_validator(mode="before")
    def validate_data(cls, values: Any) -> Any:
        name = values.kwargs.get("name")

        if name is not None and len(name) > cls.max_name_length:
            raise ValueError(f"The max length of the index name must be 30. Got {len(name)}")

        fields = values.kwargs.get("fields")
        if not isinstance(fields, (tuple, list)):
            raise ValueError("Index.fields must be a list or a tuple.")

        if fields and not all(isinstance(field, str) for field in fields):
            raise ValueError("Index.fields must contain only strings with field names.")

        if name is None:
            suffix = values.kwargs.get("suffix", cls.suffix)
            values["name"] = f"{'_'.join(fields)}_{suffix}"

        return values


@dataclass
class UniqueConstraint:
    """
    Class responsible for handling and declaring the database unique_together.
    """

    fields: List[str]

    @model_validator(mode="before")
    def validate_data(cls, values: Any) -> Any:
        fields = values.kwargs.get("fields")

        if not isinstance(fields, (tuple, list)):
            raise ValueError("UniqueConstraint.fields must be a list or a tuple.")

        if fields and not all(isinstance(field, str) for field in fields):
            raise ValueError("UniqueConstraint.fields must contain only strings with field names.")

        return values
