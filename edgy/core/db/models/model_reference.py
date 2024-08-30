from typing import ClassVar

from pydantic import BaseModel


class ModelRef(BaseModel):
    __related_name__: ClassVar[str]
