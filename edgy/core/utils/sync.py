import asyncio
import weakref
from collections.abc import Awaitable
from contextvars import ContextVar, copy_context
from threading import Event, Thread
from typing import Any, Optional

# for registry with
current_eventloop: ContextVar[Optional[asyncio.AbstractEventLoop]] = ContextVar(
    "current_eventloop", default=None
)


async def _coro_helper(awaitable: Awaitable, timeout: Optional[float]) -> Any:
    if timeout is not None and timeout > 0:
        return await asyncio.wait_for(awaitable, timeout)
    return await awaitable


weak_subloop_map: weakref.WeakKeyDictionary[
    asyncio.AbstractEventLoop, asyncio.AbstractEventLoop
] = weakref.WeakKeyDictionary()


async def _startup(old_loop: asyncio.AbstractEventLoop, is_initialized: Event) -> None:
    new_loop = asyncio.get_running_loop()
    weakref.finalize(old_loop, new_loop.stop)
    weak_subloop_map[old_loop] = new_loop
    is_initialized.set()
    # poll old loop
    while True:
        if not old_loop.is_closed():
            await asyncio.sleep(0.5)
        else:
            break
    new_loop.stop()


def _init_thread(old_loop: asyncio.AbstractEventLoop, is_initialized: Event) -> None:
    loop = asyncio.new_event_loop()
    # keep reference
    task = loop.create_task(_startup(old_loop, is_initialized))
    try:
        try:
            loop.run_forever()
        except RuntimeError:
            pass
        finally:
            # now all inits wait
            is_initialized.clear()
        loop.run_until_complete(loop.shutdown_asyncgens())
    finally:
        weak_subloop_map.pop(loop, None)
        del task
        loop.close()
        del loop


def get_subloop(loop: asyncio.AbstractEventLoop) -> asyncio.AbstractEventLoop:
    sub_loop = weak_subloop_map.get(loop)
    if sub_loop is None:
        is_initialized = Event()
        thread = Thread(target=_init_thread, args=[loop, is_initialized], daemon=True)
        thread.start()
        is_initialized.wait()
        return weak_subloop_map[loop]

    return sub_loop


def run_sync(
    awaitable: Awaitable,
    timeout: Optional[float] = None,
    *,
    loop: Optional[asyncio.AbstractEventLoop] = None,
) -> Any:
    """
    Runs the queries in sync mode
    """
    if loop is None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # in sync contexts there is no asyncio.get_running_loop()
            loop = current_eventloop.get()

    if loop is None:
        return asyncio.run(_coro_helper(awaitable, timeout))
    elif not loop.is_closed() and not loop.is_running():
        # re-use an idling loop
        return loop.run_until_complete(_coro_helper(awaitable, timeout))
    else:
        ctx = copy_context()
        # the context of the coro seems to be switched correctly
        # in case of problems, we can switch to threadexecutors with asyncio.run but this is not as performant
        return asyncio.run_coroutine_threadsafe(
            ctx.run(_coro_helper, awaitable, timeout), get_subloop(loop)
        ).result()
