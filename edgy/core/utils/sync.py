import asyncio
from typing import Any, Awaitable

import nest_asyncio

nest_asyncio.apply()


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
        # nested loop run, only possible with nest_asyncio
        return loop.run_until_complete(awaitable)
