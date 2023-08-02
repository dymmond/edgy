from typing import Any

from pydantic import BaseModel


class HashableBaseModel(BaseModel):
    """
    Pydantic BaseModel by default doesn't handle with hashable types the same way
    a python object would and therefore there are types that are mutable (list, set)
    not hashable and those need to be handled properly.

    HashableBaseModel handles those corner cases.
    """

    __slots__ = ["__weakref__"]

    def __hash__(self) -> Any:
        values: Any = {}
        for key, value in self.__dict__.items():
            values[key] = None
            if isinstance(value, (list, set)):
                values[key] = tuple(value)
            else:
                values[key] = value
        return hash((type(self),) + tuple(values))


class ArbitraryHashableBaseModel(HashableBaseModel):
    """
    Same as HashableBaseModel but allowing arbitrary values
    """

    class Config:
        extra = "allow"
        arbitrary_types_allowed = True
