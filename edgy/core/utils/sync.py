from __future__ import annotations

import asyncio
import weakref
from collections.abc import Awaitable
from contextvars import ContextVar, copy_context
from threading import Event, Thread
from typing import Any

# Context variable to store the current event loop, primarily for synchronous contexts.
current_eventloop: ContextVar[asyncio.AbstractEventLoop | None] = ContextVar(
    "current_eventloop", default=None
)


async def _coro_helper(awaitable: Awaitable, timeout: float | None) -> Any:
    """
    Helper coroutine to await a given awaitable, with an optional timeout.

    This function wraps an awaitable, providing a mechanism to enforce a timeout
    for its execution. If a timeout is specified and is positive, `asyncio.wait_for`
    is used to manage the waiting period. Otherwise, the awaitable is simply awaited.

    Parameters:
        awaitable (Awaitable): The awaitable object (e.g., a coroutine) to execute.
        timeout (float | None): The maximum time in seconds to wait for the awaitable
                                to complete. If `None` or non-positive, no timeout
                                is enforced.

    Returns:
        Any: The result of the awaited operation.

    Raises:
        asyncio.TimeoutError: If the awaitable does not complete within the specified
                              `timeout` duration.
    """
    if timeout is not None and timeout > 0:
        # Wait for the awaitable with a timeout.
        return await asyncio.wait_for(awaitable, timeout)
    # Await the awaitable without a timeout.
    return await awaitable


# A WeakKeyDictionary to map parent event loops to their corresponding sub-loops.
# WeakKeyDictionary ensures that sub-loops are garbage collected if their parent
# loops are no longer referenced.
weak_subloop_map: weakref.WeakKeyDictionary[
    asyncio.AbstractEventLoop, asyncio.AbstractEventLoop
] = weakref.WeakKeyDictionary()


async def _startup(old_loop: asyncio.AbstractEventLoop, is_initialized: Event) -> None:
    """
    Asynchronously manages the lifecycle of a new event loop and monitors the old loop.

    This coroutine runs within a newly created event loop (the "new_loop").
    It establishes a weak finalizer on the `old_loop` so that when the `old_loop`
    is garbage collected or goes out of scope, the `new_loop` will be stopped.
    It registers the `new_loop` in `weak_subloop_map` for retrieval, signals
    initialization, and then continuously polls the `old_loop` until it is closed,
    after which it stops itself.

    Parameters:
        old_loop (asyncio.AbstractEventLoop): The parent event loop that initiated
                                              the creation of this sub-loop.
        is_initialized (threading.Event): An event object used to signal when
                                          the new event loop has been successfully
                                          initialized and is running.
    """
    # Get the currently running event loop (which is the new sub-loop).
    new_loop = asyncio.get_running_loop()
    # Register a finalizer: when old_loop is garbage collected, new_loop.stop() will be called.
    weakref.finalize(old_loop, new_loop.stop)
    # Map the old loop to the new loop in the weak reference dictionary.
    weak_subloop_map[old_loop] = new_loop
    # Signal that the new loop has been initialized and is ready.
    is_initialized.set()
    # Continuously poll the old loop to check if it's still open.
    while True:
        if not old_loop.is_closed():
            # If the old loop is still open, yield control to allow other tasks to run.
            await asyncio.sleep(0.5)
        else:
            # If the old loop is closed, break out of the polling loop.
            break
    # Stop the new loop once the old loop is closed.
    new_loop.stop()


def _init_thread(old_loop: asyncio.AbstractEventLoop, is_initialized: Event) -> None:
    """
    Initializes and runs a new event loop in a separate thread.

    This function is designed to be the target of a `threading.Thread`. It creates
    a new `asyncio` event loop, sets it as the current loop for the thread, and
    then runs the `_startup` coroutine within it. It manages the lifecycle
    of this new loop, including graceful shutdown and cleanup, ensuring that
    resources are properly released.

    Parameters:
        old_loop (asyncio.AbstractEventLoop): The event loop from which this
                                              thread was spawned (the parent loop).
        is_initialized (threading.Event): An event object used to signal back to
                                          the calling thread when the new loop
                                          has started and is ready.
    """
    # Create a new event loop for this thread.
    loop = asyncio.new_event_loop()
    # Set the new loop as the current event loop for this thread.
    asyncio.set_event_loop(loop)
    # Create a task to run the _startup coroutine within this new loop.
    # Keep a reference to the task to prevent it from being garbage collected prematurely.
    task = loop.create_task(_startup(old_loop, is_initialized))
    try:
        try:
            # Run the loop indefinitely until stop() is called.
            loop.run_forever()
        except RuntimeError:
            # Catch RuntimeError that can occur if run_forever is called on a stopped loop.
            pass
        finally:
            # Signal that initialization is no longer active (e.g., for subsequent startups).
            is_initialized.clear()
            # Shut down asynchronous generators gracefully.
            loop.run_until_complete(loop.shutdown_asyncgens())
    finally:
        # Remove the loop from the weak reference map upon thread exit.
        weak_subloop_map.pop(loop, None)
        # Explicitly delete the task and loop references to aid garbage collection.
        del task
        loop.close()
        del loop


def get_subloop(loop: asyncio.AbstractEventLoop) -> asyncio.AbstractEventLoop:
    """
    Retrieves or creates a dedicated sub-event loop for running coroutines
    from another event loop.

    This function checks if a sub-loop already exists for the given parent `loop`
    in `weak_subloop_map`. If not, it creates a new thread, initializes an
    event loop within it, starts the loop, and waits for it to signal
    initialization before returning the sub-loop. This mechanism allows
    synchronous calls to be made from an asynchronous context without blocking
    the main event loop.

    Parameters:
        loop (asyncio.AbstractEventLoop): The parent event loop for which to
                                          retrieve or create a sub-loop.

    Returns:
        asyncio.AbstractEventLoop: The active sub-event loop associated with
                                   the provided parent loop.
    """
    # Try to get an existing sub-loop from the map.
    sub_loop = weak_subloop_map.get(loop)
    if sub_loop is None:
        # If no sub-loop exists, create an Event to synchronize thread startup.
        is_initialized = Event()
        # Create and start a new daemon thread to run the sub-loop.
        thread = Thread(target=_init_thread, args=[loop, is_initialized], daemon=True)
        thread.start()
        # Wait for the sub-loop to signal that it has been initialized.
        is_initialized.wait()
        # Return the newly created and initialized sub-loop.
        return weak_subloop_map[loop]

    # Return the existing sub-loop.
    return sub_loop


def run_sync(
    awaitable: Awaitable,
    timeout: float | None = None,
    *,
    loop: asyncio.AbstractEventLoop | None = None,
) -> Any:
    """
    Executes an awaitable (coroutine) synchronously.

    This function provides a flexible way to run an `Awaitable` in a synchronous
    manner. It attempts to use an existing event loop if available. If no loop
    is running, it starts a new one using `asyncio.run()`. If a loop is running
    but not closed, it either reuses an idling loop or uses a dedicated sub-loop
    in a separate thread to prevent blocking the main event loop. Context variables
    are copied to ensure proper execution context.

    Parameters:
        awaitable (Awaitable): The coroutine or awaitable object to be executed.
        timeout (float | None, optional): The maximum time in seconds to wait for
                                          the awaitable to complete. If `None` or
                                          non-positive, no timeout is enforced.
                                          Defaults to `None`.
        loop (asyncio.AbstractEventLoop | None, optional): An explicit event loop
                                                            to use. If `None`, the
                                                            function will try to get
                                                            the current running loop
                                                            or a default one.
                                                            Defaults to `None`.

    Returns:
        Any: The result returned by the `awaitable` upon completion.

    Raises:
        asyncio.TimeoutError: If the operation times out.
        RuntimeError: If `asyncio.run` is called in an already running event loop,
                      and no other suitable loop or sub-loop can be used.
    """
    if loop is None:
        try:
            # Attempt to get the currently running event loop.
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # If no loop is running (e.g., in a synchronous context), get from context var.
            loop = current_eventloop.get()

    if loop is None:
        # If no event loop is found, run the awaitable in a new, temporary loop.
        return asyncio.run(_coro_helper(awaitable, timeout))
    elif not loop.is_closed() and not loop.is_running():
        # If a loop exists but is not running, re-use it.
        return loop.run_until_complete(_coro_helper(awaitable, timeout))
    else:
        # If the loop is running, copy the current context for the coroutine execution.
        ctx = copy_context()
        # Run the coroutine in a separate sub-loop thread to avoid blocking the main loop.
        # The context is explicitly run to ensure context variables are propagated.
        return asyncio.run_coroutine_threadsafe(
            ctx.run(_coro_helper, awaitable, timeout), get_subloop(loop)
        ).result()
