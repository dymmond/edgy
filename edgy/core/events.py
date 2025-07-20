from __future__ import annotations

import inspect
import typing
from collections.abc import Callable, Sequence
from typing import Any, TypeVar

# Type alias for a mutable mapping representing the ASGI scope.
Scope = typing.MutableMapping[str, typing.Any]
# Type alias for a mutable mapping representing an ASGI message.
Message = typing.MutableMapping[str, typing.Any]

# Type alias for an ASGI Receive callable, which is an awaitable that returns a Message.
Receive = typing.Callable[[], typing.Awaitable[Message]]
# Type alias for an ASGI Send callable, which is an awaitable that takes a Message.
Send = typing.Callable[[Message], typing.Awaitable[None]]

# Type variable for generic class methods.
_T = TypeVar("_T")


class AyncLifespanContextManager:
    """
    Manages and handles application startup (`on_startup`) and shutdown (`on_shutdown`)
    events in an Edgy-compatible asynchronous context manager.

    This class provides a modern approach to managing application lifecycle events,
    aligning with the ASGI lifespan protocol. It replaces the older, deprecated
    `on_startup` and `on_shutdown` lists previously used in frameworks like Starlette
    by integrating them into an asynchronous context manager. This allows for
    setup and teardown logic to be executed reliably at the beginning and end
    of the application's lifespan.

    Attributes:
        on_startup (list[Callable[..., Any]]): A list of callable functions or
            coroutines to be executed when the application starts up.
        on_shutdown (list[Callable[..., Any]]): A list of callable functions or
            coroutines to be executed when the application shuts down.
    """

    def __init__(
        self,
        on_shutdown: Sequence[Callable[..., Any]] | None = None,
        on_startup: Sequence[Callable[..., Any]] | None = None,
    ) -> None:
        """
        Initializes the AyncLifespanContextManager with startup and shutdown handlers.

        Parameters:
            on_shutdown (Sequence[Callable[..., Any]] | None, optional): A sequence
                of callables to run during application shutdown. Each callable
                can be a regular function or an awaitable coroutine. Defaults to `None`.
            on_startup (Sequence[Callable[..., Any]] | None, optional): A sequence
                of callables to run during application startup. Each callable
                can be a regular function or an awaitable coroutine. Defaults to `None`.
        """
        # Convert sequences to lists to ensure mutability and consistent handling.
        self.on_startup = [] if on_startup is None else list(on_startup)
        self.on_shutdown = [] if on_shutdown is None else list(on_shutdown)

    def __call__(self: _T, app: object) -> _T:
        """
        Allows the context manager to be called with an application instance,
        returning itself.

        This method makes the context manager compatible with certain ASGI lifespan
        implementations that expect the lifespan context manager to be callable
        with the application instance.

        Parameters:
            app (object): The application instance (e.g., an ASGI application).

        Returns:
            _T: The instance of the AyncLifespanContextManager itself.
        """
        return self

    async def __aenter__(self) -> None:
        """
        Asynchronously enters the runtime context, executing all `on_startup` handlers.

        When the application starts, this method is invoked. It iterates through
        all registered `on_startup` callables. If a handler is an awaitable (a coroutine),
        it is awaited; otherwise, it is simply called.
        """
        for handler in self.on_startup:
            result = handler()
            # If the handler returns an awaitable, await it.
            if inspect.isawaitable(result):
                await result

    async def __aexit__(self, scope: Scope, receive: Receive, send: Send, **kwargs: Any) -> None:
        """
        Asynchronously exits the runtime context, executing all `on_shutdown` handlers.

        When the application shuts down, this method is invoked. It iterates through
        all registered `on_shutdown` callables. If a handler is an awaitable (a coroutine),
        it is awaited; otherwise, it is simply called.

        Parameters:
            scope (Scope): The ASGI scope dictionary.
            receive (Receive): The ASGI receive callable.
            send (Send): The ASGI send callable.
            **kwargs (Any): Additional keyword arguments passed during context exit.
        """
        for handler in self.on_shutdown:
            result = handler()
            # If the handler returns an awaitable, await it.
            if inspect.isawaitable(result):
                await result


def handle_lifespan_events(
    on_startup: Sequence[Callable] | None = None,
    on_shutdown: Sequence[Callable] | None = None,
    lifespan: Any | None = None,
) -> Any:
    """
    Handles and consolidates lifespan event configurations for ASGI applications.

    This function provides a flexible mechanism to manage lifespan events, supporting
    both the traditional `on_startup` and `on_shutdown` lists (for legacy and
    comprehension) as well as a direct `lifespan` context manager. It acts as
    an adapter, prioritizing the modern `lifespan` context manager if provided,
    otherwise creating one from the `on_startup` and `on_shutdown` lists.

    Parameters:
        on_startup (Sequence[Callable] | None, optional): A sequence of callable
            functions or coroutines to execute during application startup.
            Defaults to `None`.
        on_shutdown (Sequence[Callable] | None, optional): A sequence of callable
            functions or coroutines to execute during application shutdown.
            Defaults to `None`.
        lifespan (Any | None, optional): An existing ASGI lifespan context manager
            instance. If provided, this takes precedence over `on_startup` and
            `on_shutdown` lists. Defaults to `None`.

    Returns:
        Any: An instance of `AyncLifespanContextManager` if `on_startup` or
             `on_shutdown` lists are provided, or the `lifespan` object itself
             if provided. Returns `None` if no lifespan events are configured.
    """
    # If startup or shutdown handlers are provided, create a new AyncLifespanContextManager.
    if on_startup or on_shutdown:
        return AyncLifespanContextManager(on_startup=on_startup, on_shutdown=on_shutdown)
    # If a direct lifespan context manager is provided, use it.
    elif lifespan:
        return lifespan
    # If no lifespan events are configured, return None.
    return None
