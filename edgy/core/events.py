import inspect
import typing
from collections.abc import Callable, Sequence
from typing import Any, TypeVar

Scope = typing.MutableMapping[str, typing.Any]
Message = typing.MutableMapping[str, typing.Any]

Receive = typing.Callable[[], typing.Awaitable[Message]]
Send = typing.Callable[[Message], typing.Awaitable[None]]

_T = TypeVar("_T")


class AyncLifespanContextManager:
    """
    Manages and handles the on_startup and on_shutdown events
    in an Esmerald way.

    This is not the same as the on_startup and on_shutdown
    from Starlette. Those are now deprecated and will be removed
    in the version 1.0 of Starlette.

    This aims to provide a similar functionality but by generating
    a lifespan event based on the values from the on_startup and on_shutdown
    lists.
    """

    def __init__(
        self,
        on_shutdown: Sequence[Callable[..., Any]] | None = None,
        on_startup: Sequence[Callable[..., Any]] | None = None,
    ) -> None:
        self.on_startup = [] if on_startup is None else list(on_startup)
        self.on_shutdown = [] if on_shutdown is None else list(on_shutdown)

    def __call__(self: _T, app: object) -> _T:
        return self

    async def __aenter__(self) -> None:
        """Runs the functions on startup"""
        for handler in self.on_startup:
            result = handler()
            if inspect.isawaitable(result):
                await result

    async def __aexit__(self, scope: Scope, receive: Receive, send: Send, **kwargs: Any) -> None:
        """Runs the functions on shutdown"""
        for handler in self.on_shutdown:
            result = handler()
            if inspect.isawaitable(result):
                await result


def handle_lifespan_events(
    on_startup: Sequence[Callable] | None = None,
    on_shutdown: Sequence[Callable] | None = None,
    lifespan: Any | None = None,
) -> Any:
    """Handles with the lifespan events in the new Starlette format of lifespan.
    This adds a mask that keeps the old `on_startup` and `on_shutdown` events variable
    declaration for legacy and comprehension purposes and build the async context manager
    for the lifespan.
    """
    if on_startup or on_shutdown:
        return AyncLifespanContextManager(on_startup=on_startup, on_shutdown=on_shutdown)
    elif lifespan:
        return lifespan
    return None
