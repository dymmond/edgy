from typing import TYPE_CHECKING, Type

from pydantic import BaseModel

if TYPE_CHECKING:
    from edgy.core.db.models.model import Model


class ModelRef(BaseModel):
    __model__: Type["Model"]
