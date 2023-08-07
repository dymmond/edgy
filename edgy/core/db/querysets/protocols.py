import typing

if typing.TYPE_CHECKING:
    from edgy.core.db.models import Model

# Create a var type for the Edgy Model
EdgyModel = typing.TypeVar("EdgyModel", bound="Model")


class AwaitableQuery(typing.Generic[EdgyModel]):
    __slots__ = ("model_class",)

    def __init__(self, model_class: typing.Type[EdgyModel]) -> None:
        self.model_class: typing.Type[EdgyModel] = model_class

    async def execute(self) -> typing.Any:
        raise NotImplementedError()
