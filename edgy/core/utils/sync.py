import asyncio
from typing import Any, Awaitable


def run_sync(async_function: Awaitable) -> Any:
    """
    Runs the queries in sync mode
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop:
        return loop.run_until_complete(async_function)
    else:
        return asyncio.run(async_function)
