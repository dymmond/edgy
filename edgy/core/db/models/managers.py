from pydantic import BaseModel, ConfigDict


class Manager(BaseModel):
    """
    Base manager of all Edgy managers applied.
    """

    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)
