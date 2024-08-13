import asyncio
from typing import Any, Awaitable


async def _await_helper(awaitable: Awaitable) -> Any:
    return await awaitable


def run_sync(awaitable: Awaitable) -> Any:
    """
    Runs the queries in sync mode
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop is None:
        return asyncio.run(awaitable)
    else:
        task = loop.create_task(_await_helper(awaitable))
        loop.run_until_complete(task)
        return task.result()
