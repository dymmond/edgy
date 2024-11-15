from typing import Any
from edgy import EdgySettings


@dataclass
class Extension(ExtensionProtocol[edgy.Instance, edgy.Registry]):
    name: str = "hello"

    def apply(self, monkay_instance: Monkay[edgy.Instance, edgy.Registry]) -> None:
        """Do something here"""


@dataclass
class ExtensionLessTyped(ExtensionProtocol):
    name: str = "hello"

    def apply(self, monkay_instance: Monkay) -> None:
        """Do something here"""


class ExtensionSettings(EdgySettings):
    extensions: list[Any] = [Extension(), ExtensionLessTyped()]
