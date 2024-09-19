from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Dict

if TYPE_CHECKING:
    from edgy.core.connection.registry import Registry

ASGIApp = Callable[
    [
        Dict[str, Any],
        Callable[[], Awaitable[Dict[str, Any]]],
        Callable[[Dict[str, Any]], Awaitable[None]],
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
        scope: Dict[str, Any],
        receive: Callable[[], Awaitable[Dict[str, Any]]],
        send: Callable[[Dict[str, Any]], Awaitable[None]],
    ) -> None:
        if scope["type"] == "lifespan":
            original_receive = receive

            async def receive() -> Dict[str, Any]:
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
