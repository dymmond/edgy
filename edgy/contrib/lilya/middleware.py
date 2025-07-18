from __future__ import annotations

from typing import TYPE_CHECKING, cast

import edgy

if TYPE_CHECKING:
    from lilya.protocols.middleware import MiddlewareProtocol
    from lilya.types import ASGIApp, Receive, Scope, Send

    from edgy.conf.global_settings import EdgySettings
    from edgy.core.connection import Registry
else:
    MiddlewareProtocol = object


class EdgyMiddleware(MiddlewareProtocol):
    def __init__(
        self,
        app: ASGIApp,
        registry: Registry | None = None,
        settings: EdgySettings | None = None,
        wrap_asgi_app: bool = True,
    ) -> None:
        self.app = app
        self.overwrite: dict = {}
        if registry is not None:
            if wrap_asgi_app:
                self.app = cast("ASGIApp", registry.asgi(self.app))  # type: ignore
            self.overwrite["instance"] = edgy.Instance(registry=registry, app=self.app)
        if settings is not None:
            self.overwrite["settings"] = settings

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        with edgy.monkay.with_full_overwrite(**self.overwrite):
            await self.app(scope, receive, send)
