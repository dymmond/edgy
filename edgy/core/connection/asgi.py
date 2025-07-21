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
    """
    A custom exception designed to silently interrupt the ASGI lifespan process
    without propagating an error externally. This is particularly useful for
    handling startup or shutdown failures within the lifespan protocol where
    the ASGI specification requires sending a specific message (e.g.,
    'lifespan.startup.failed') and then effectively stopping the lifespan
    handler without further processing.
    """

    pass


@dataclass
class ASGIHelper:
    """
    A helper class designed to wrap an ASGI application and integrate it with
    an Edgy registry's asynchronous lifecycle management, specifically for
    handling database connections and disconnections during the ASGI lifespan
    events. It can optionally take over the full `lifespan` protocol handling.

    Attributes:
        app (ASGIApp): The original ASGI application to be wrapped. This
                       application will receive the modified `receive` callable
                       if `handle_lifespan` is True, or will be called directly
                       otherwise.
        registry (Registry): An instance of the Edgy `Registry` class,
                             responsible for managing database connections.
                             This registry's `__aenter__` and `__aexit__`
                             methods are called during `lifespan.startup` and
                             `lifespan.shutdown` events, respectively.
        handle_lifespan (bool): A flag indicating whether this helper should
                                fully manage the ASGI `lifespan` scope.
                                If True, it will intercept `lifespan.startup`
                                and `lifespan.shutdown` messages, call the
                                registry's lifecycle methods, and send the
                                corresponding `lifespan.startup.complete` or
                                `lifespan.shutdown.complete` messages. If False,
                                the registry's methods are still called, but
                                the original `app` is responsible for sending
                                the complete messages. Defaults to False.
    """

    app: ASGIApp
    registry: Registry
    handle_lifespan: bool = False

    async def __call__(
        self,
        scope: MutableMapping[str, Any],
        receive: Callable[[], Awaitable[MutableMapping[str, Any]]],
        send: Callable[[MutableMapping[str, Any]], Awaitable[None]],
    ) -> None:
        """
        The core ASGI callable method, making instances of ASGIHelper directly
        callable as an ASGI application. This method intercepts and processes
        ASGI scopes, especially focusing on the 'lifespan' scope to manage
        database connections via the Edgy registry.

        Args:
            scope (MutableMapping[str, Any]): The ASGI scope dictionary,
                                                containing information about
                                                the connection and request.
                                                E.g., `{"type": "lifespan"}`
                                                or `{"type": "http"}`.
            receive (Callable[[], Awaitable[MutableMapping[str, Any]]]): An
                asynchronous callable that receives messages from the ASGI
                server. For `lifespan` scope, this will yield messages like
                `{"type": "lifespan.startup"}`.
            send (Callable[[MutableMapping[str, Any]], Awaitable[None]]): An
                asynchronous callable that sends messages to the ASGI server.
                Used to send responses or lifecycle status updates like
                `{"type": "lifespan.startup.complete"}`.
        """
        # Check if the current scope is of type 'lifespan'.
        if scope["type"] == "lifespan":
            # Store the original receive callable to be used inside the wrapper.
            original_receive = receive

            async def receive() -> MutableMapping[str, Any]:
                """
                A wrapped `receive` callable that intercepts 'lifespan.startup'
                and 'lifespan.shutdown' messages to trigger the Edgy registry's
                asynchronous entry and exit methods.
                """
                # Await the message from the original receive callable.
                message = await original_receive()
                # Check if the message type is for lifespan startup.
                if message["type"] == "lifespan.startup":
                    try:
                        # Attempt to enter the registry's asynchronous context,
                        # typically establishing database connections.
                        await self.registry.__aenter__()
                    except Exception as exc:
                        # If an exception occurs during startup, send a failed
                        # message to the ASGI server.
                        await send({"type": "lifespan.startup.failed", "msg": str(exc)})
                        # Raise a custom exception to stop further lifespan
                        # processing for this event.
                        raise MuteInteruptException from None
                # Check if the message type is for lifespan shutdown.
                elif message["type"] == "lifespan.shutdown":
                    try:
                        # Attempt to exit the registry's asynchronous context,
                        # typically closing database connections.
                        await self.registry.__aexit__()
                    except Exception as exc:
                        # If an exception occurs during shutdown, send a failed
                        # message to the ASGI server.
                        await send({"type": "lifespan.shutdown.failed", "msg": str(exc)})
                        # Raise a custom exception to stop further lifespan
                        # processing for this event.
                        raise MuteInteruptException from None
                # Return the original message after processing.
                return message

            # If `handle_lifespan` is True, this helper will fully manage
            # the lifespan protocol, including sending 'complete' messages.
            if self.handle_lifespan:
                # Suppress the MuteInteruptException to gracefully stop
                # the lifespan loop without uncaught exceptions.
                with suppress(MuteInteruptException):
                    # Continuously receive and process lifespan messages.
                    while True:
                        # Await the next lifespan message.
                        message = await receive()
                        # If it's a startup message, send a complete message.
                        if message["type"] == "lifespan.startup":
                            await send({"type": "lifespan.startup.complete"})
                        # If it's a shutdown message, send a complete message
                        # and break the loop.
                        elif message["type"] == "lifespan.shutdown":
                            await send({"type": "lifespan.shutdown.complete"})
                            break
                # Once lifespan handling is complete, return from the callable.
                return

        # For any scope type other than 'lifespan', or if handle_lifespan
        # is False (meaning the original app will handle 'complete' messages),
        # or after the lifespan handling is complete, call the original ASGI app.
        # Suppress MuteInteruptException in case it was raised by the
        # modified receive callable and propagated here.
        with suppress(MuteInteruptException):
            await self.app(scope, receive, send)

    def __getattr__(self, key: str) -> Any:
        """
        Provides attribute access proxying to the underlying ASGI application.
        This method is particularly useful for frameworks like Esmerald that
        might directly access attributes (e.g., `app.router`, `app.middleware`)
        from the wrapped ASGI application instance.

        Args:
            key (str): The name of the attribute being accessed.

        Returns:
            Any: The value of the attribute from the wrapped ASGI application.
        """
        # Return the attribute from the wrapped ASGI application.
        return getattr(self.app, key)
