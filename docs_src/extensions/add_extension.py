from dataclasses import dataclass

import edgy


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


edgy.monkay.add_extension(Extension())

edgy.monkay.add_extension(ExtensionLessTyped())
