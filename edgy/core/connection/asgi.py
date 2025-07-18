from __future__ import annotations

from collections.abc import Awaitable, Callable, MutableMapping
from contextlib import suppress
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from edgy.core.connection.registry import Registry

ASGIApp = Callable[
    [
        MutableMapping[str, Any],
        Callable[[], Awaitable[MutableMapping[str, Any]]],
        Callable[[MutableMapping[str, Any]], Awaitable[None]],
    ],
    Awaitable[None],
]


class MuteInteruptException(BaseException):
    pass


@dataclass
class ASGIHelper:
    app: ASGIApp
    registry: Registry
    handle_lifespan: bool = False

    async def __call__(
        self,
        scope: MutableMapping[str, Any],
        receive: Callable[[], Awaitable[MutableMapping[str, Any]]],
        send: Callable[[MutableMapping[str, Any]], Awaitable[None]],
    ) -> None:
        if scope["type"] == "lifespan":
            original_receive = receive

            async def receive() -> MutableMapping[str, Any]:
                message = await original_receive()
                if message["type"] == "lifespan.startup":
                    try:
                        await self.registry.__aenter__()
                    except Exception as exc:
                        await send({"type": "lifespan.startup.failed", "msg": str(exc)})
                        raise MuteInteruptException from None
                elif message["type"] == "lifespan.shutdown":
                    try:
                        await self.registry.__aexit__()
                    except Exception as exc:
                        await send({"type": "lifespan.shutdown.failed", "msg": str(exc)})
                        raise MuteInteruptException from None
                return message

            if self.handle_lifespan:
                with suppress(MuteInteruptException):
                    while True:
                        message = await receive()
                        if message["type"] == "lifespan.startup":
                            await send({"type": "lifespan.startup.complete"})
                        elif message["type"] == "lifespan.shutdown":
                            await send({"type": "lifespan.shutdown.complete"})
                            break
                return

        with suppress(MuteInteruptException):
            await self.app(scope, receive, send)

    def __getattr__(self, key: str) -> Any:
        # esmerald shim, they extract data directly from app.
        return getattr(self.app, key)
