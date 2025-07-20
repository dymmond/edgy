from __future__ import annotations

from typing import Any

from blinker import Signal

from edgy.exceptions import SignalError

# Define standard lifecycle signals using Blinker's Signal class.
# These signals are used to dispatch events before/after database operations.
post_delete = Signal()
post_save = Signal()
post_update = Signal()
pre_delete = Signal()
post_migrate = Signal()
pre_save = Signal()
pre_update = Signal()
pre_migrate = Signal()


class Broadcaster(dict):
    """
    A dictionary-like class that acts as a central hub for managing Blinker signals.

    This class provides a convenient way to access and set `blinker.Signal` instances
    using attribute-style access. If a signal does not exist when accessed, it is
    automatically created and set, ensuring a consistent interface for signal management.
    It also enforces that only `Signal` objects can be assigned as attributes.
    """

    def __getattr__(self, item: str) -> Signal:
        """
        Retrieves a signal by its name. If the signal does not exist, it creates
        a new `blinker.Signal` and adds it to the broadcaster.

        Parameters:
            item (str): The name of the signal to retrieve or create.

        Returns:
            Signal: The `blinker.Signal` instance corresponding to the given name.
        """
        # Use setdefault to return the signal if it exists, otherwise create and set it.
        return self.setdefault(item, Signal())  # type: ignore

    def __setattr__(self, __name: str, __value: Signal) -> None:
        """
        Sets a signal with the given name. Enforces that only `blinker.Signal`
        instances can be assigned.

        Parameters:
            __name (str): The name of the signal attribute to set.
            __value (Signal): The `blinker.Signal` instance to assign.

        Raises:
            SignalError: If the provided `__value` is not an instance of `blinker.Signal`.
        """
        if not isinstance(__value, Signal):
            # Raise an error if the value is not a valid Blinker Signal.
            raise SignalError(f"{__value} is not valid signal")
        # Store the signal in the underlying dictionary.
        self[__name] = __value

    def set_lifecycle_signals_from(self, namespace: Any, overwrite: bool = True) -> None:
        """
        Sets or defaults lifecycle signals from a given namespace object.

        This method is useful for importing and configuring a predefined set of
        lifecycle signals (e.g., from a model or a module) into the `Broadcaster`
        instance. It iterates through common lifecycle signal names and either
        overwrites existing signals or sets them if they don't already exist.

        Parameters:
            namespace (Any): An object or module from which to retrieve the lifecycle
                             signals. This object should have attributes matching
                             the signal names (e.g., `post_save`).
            overwrite (bool): If `True`, existing signals in the broadcaster will be
                              overwritten by those from the namespace. If `False`,
                              signals will only be set if they don't already exist
                              (using `setdefault`). Defaults to `True`.
        """
        # List of common lifecycle signal names to process.
        for name in (
            "post_delete",
            "post_save",
            "post_update",
            "pre_delete",
            "pre_save",
            "pre_update",
        ):
            if overwrite:
                # Overwrite the signal if 'overwrite' is True.
                setattr(self, name, getattr(namespace, name))
            else:
                # Set the signal only if it doesn't already exist.
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
