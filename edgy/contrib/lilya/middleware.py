from __future__ import annotations

from typing import TYPE_CHECKING

from lilya.protocols.middleware import MiddlewareProtocol

import edgy

if TYPE_CHECKING:
    from lilya.types import ASGIApp, Receive, Scope, Send

    from edgy.conf.global_settings import EdgySettings
    from edgy.core.connection import Registry


class EdgyMiddleware(MiddlewareProtocol):
    """
    Lilya middleware designed to integrate Edgy's registry and settings
    into an ASGI application's scope.

    This middleware allows for the dynamic injection of an Edgy `Registry`
    and `EdgySettings` instance, enabling multi-tenancy and other Edgy
    features to be contextually available within the ASGI application.
    It can also wrap the ASGI application with the registry's ASGI capabilities.
    """

    def __init__(
        self,
        app: ASGIApp,
        registry: Registry | None = None,
        settings: EdgySettings | None = None,
        wrap_asgi_app: bool = True,
    ) -> None:
        """
        Initializes the EdgyMiddleware.

        Args:
            app (ASGIApp): The ASGI application to wrap.
            registry (Registry | None, optional): An Edgy `Registry` instance
                                                  to be made available in the
                                                  application context.
                                                  Defaults to `None`.
            settings (EdgySettings | None, optional): An `EdgySettings` instance
                                                      to be made available in the
                                                      application context.
                                                      Defaults to `None`.
            wrap_asgi_app (bool, optional): If `True` and a `registry` is provided,
                                            the ASGI application will be wrapped
                                            with the registry's ASGI capabilities.
                                            This is typically used for database
                                            connection management. Defaults to `True`.
        """
        self.app = app
        self.overwrite: dict = {}  # Dictionary to store objects for monkey patching.

        if registry is not None:
            if wrap_asgi_app:
                # Wrap the ASGI app with the registry's ASGI capabilities.
                # This often involves managing database connections per request.
                self.app = registry.asgi(self.app)
            # Store an Edgy `Instance` containing the registry and the wrapped app.
            # This instance will be available via monkey patching.
            self.overwrite["instance"] = edgy.Instance(registry=registry, app=self.app)
        if settings is not None:
            # Store the provided settings instance for monkey patching.
            self.overwrite["settings"] = settings

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """
        The ASGI callable method that processes incoming requests.

        This method uses `edgy.monkay.with_full_overwrite` to temporarily
        inject the configured registry and settings into the Edgy context
        for the duration of the request.

        Args:
            scope (Scope): The ASGI scope dictionary.
            receive (Receive): The ASGI receive callable.
            send (Send): The ASGI send callable.
        """
        # Use a context manager to apply the overwrites (monkey patching)
        # for the duration of the ASGI call. This makes the `instance`
        # and `settings` globally accessible within the Edgy context
        # for the current request.
        with edgy.monkay.with_full_overwrite(**self.overwrite):
            # Pass the control to the next ASGI application in the stack.
            await self.app(scope, receive, send)
