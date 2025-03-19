from typing import Any

from blinker import Signal

from edgy.exceptions import SignalError

post_delete = Signal()
post_save = Signal()
post_update = Signal()
pre_delete = Signal()
post_migrate = Signal()
pre_save = Signal()
pre_update = Signal()
pre_migrate = Signal()


class Broadcaster(dict):
    def __getattr__(self, item: str) -> Signal:
        return self.setdefault(item, Signal())  # type: ignore

    def __setattr__(self, __name: str, __value: Signal) -> None:
        if not isinstance(__value, Signal):
            raise SignalError(f"{__value} is not valid signal")
        self[__name] = __value

    def set_lifecycle_signals_from(self, namespace: Any, overwrite: bool = True) -> None:
        for name in (
            "post_delete",
            "post_save",
            "post_update",
            "pre_delete",
            "pre_save",
            "pre_update",
        ):
            if overwrite:
                setattr(self, name, getattr(namespace, name))
            else:
                self.setdefault(name, getattr(namespace, name))


__all__ = [
    "Signal",
    "Broadcaster",
    "post_delete",
    "post_save",
    "post_update",
    "post_migrate",
    "pre_delete",
    "pre_save",
    "pre_update",
    "pre_migrate",
]
