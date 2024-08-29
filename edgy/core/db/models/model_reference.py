from typing import TYPE_CHECKING, ClassVar, Optional, Type, Union

from pydantic import BaseModel

if TYPE_CHECKING:
    from edgy.core.db.models.model import Model


class ModelRef(BaseModel):
    __model__: ClassVar[Union[Type["Model"], str]]
    __foreign_key__: ClassVar[Optional[str]] = None
