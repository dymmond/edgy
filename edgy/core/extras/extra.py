from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from edgy.cli.constants import EDGY_DB, EDGY_EXTRA
from edgy.core.extras.base import BaseExtra
from edgy.core.terminal import Print, Terminal

if TYPE_CHECKING:
    from edgy.core.connection.registry import Registry

terminal = Terminal()
printer = Print()


@dataclass
class Config:
    app: Any
    registry: "Registry"


class EdgyExtra(BaseExtra):
    """
    Shim which can be used for cli applications instead of Migrate.
    """

    def __init__(self, app: Any, registry: "Registry", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.app = app
        self.registry = registry

        # this is how the magic works. We inject a config in app.
        self.set_edgy_extension(self.app, self.registry)

    def set_edgy_extension(self, app: Any, registry: "Registry") -> None:  # type: ignore[override]
        """
        Sets a edgy dictionary for the app object.
        """
        if hasattr(app, EDGY_DB):
            printer.write_warning(
                "The application already has a Migrate related configuration with the needed information. EdgyExtra will be ignored and it can be removed."
            )
            return

        config = Config(app=app, registry=registry)
        # bypass __setattr__ method
        object.__setattr__(app, EDGY_EXTRA, {"extra": config})
