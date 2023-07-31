import functools
from typing import Any

import anyio
from anyio._core._eventloop import threadlocals


def execsync(async_function: Any, raise_error: bool = True) -> Any:
    """
    Runs any async function inside a blocking function (sync).
    """

    @functools.wraps(async_function)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        current_async_module = getattr(threadlocals, "current_async_module", None)
        partial_func = functools.partial(async_function, *args, **kwargs)
        if current_async_module is not None and raise_error is True:
            return anyio.from_thread.run(partial_func)
        return anyio.run(partial_func)

    return wrapper
