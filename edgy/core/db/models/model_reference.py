from typing import TYPE_CHECKING, Type, Union

from pydantic import BaseModel

if TYPE_CHECKING:
    from edgy.core.db.models.model import Model


class ModelRef(BaseModel):
    __model__: Union[Type["Model"], str]
