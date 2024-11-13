from typing import TYPE_CHECKING, Any

import edgy

if TYPE_CHECKING:
    from edgy.core.connection.registry import Registry


class EdgyExtra:
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
        edgy.monkay.set_instance(edgy.Instance(registry, app))
