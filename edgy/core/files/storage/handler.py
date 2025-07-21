from typing import TYPE_CHECKING, Any

from monkay import load

from edgy.conf import settings
from edgy.exceptions import InvalidStorageError

if TYPE_CHECKING:
    from edgy.core.files.storage.base import Storage


class StorageHandler:
    """
    Manages and provides access to various file storage backends configured
    within the Edgy system. It acts as a central registry for storage instances,
    allowing them to be retrieved by an alias. This handler ensures that storage
    backends are initialized only once per alias and provides a mechanism for
    creating new storage instances based on configuration.
    """

    def __init__(self, backends: dict[str, Any] | None = None) -> None:
        """
        Initializes the StorageHandler.

        Args:
            backends (dict[str, Any] | None): An optional dictionary of storage backend
                                              configurations. If None, the configurations
                                              will be loaded from `settings.storages`.
                                              Defaults to None.
        """
        self._backends = backends
        # Dictionary to store initialized storage instances, keyed by their alias.
        self._storages: dict[str, Storage] = {}

    @property
    def backends(self) -> dict[str, Any]:
        """
        Returns the dictionary of storage backend configurations.
        If not already loaded, it copies the configurations from `settings.storages`.

        Returns:
            dict[str, Any]: A dictionary where keys are storage aliases and values
                            are their configuration dictionaries.
        """
        if self._backends is None:
            self._backends = settings.storages.copy()
        return self._backends

    def __copy__(self) -> "StorageHandler":
        """
        Creates a shallow copy of the StorageHandler instance.
        This ensures that the new handler shares the same backend configurations
        but maintains its own internal state for initialized storage instances.

        Returns:
            "StorageHandler": A new StorageHandler instance.
        """
        return StorageHandler(self._backends)

    def __getitem__(self, alias: str) -> "Storage":
        """
        Retrieves a storage instance by its alias. If the storage instance
        has already been created, it returns the existing instance from the cache.
        Otherwise, it creates a new instance based on the configuration and caches it.

        Args:
            alias (str): The alias (name) of the storage backend to retrieve.

        Returns:
            "Storage": The initialized storage instance.

        Raises:
            InvalidStorageError: If the `alias` is not found in the configured
                                 `settings.STORAGES` or if the backend specified
                                 in its configuration cannot be imported.
        """
        # Attempt to retrieve the storage instance from the internal cache.
        storage = self._storages.get(alias, None)
        if storage is not None:
            return storage

        # If not found in cache, get the parameters for the storage from the backends.
        params = self.backends.get(alias, None)
        if params is None:
            # Raise an error if the alias is not configured.
            raise InvalidStorageError(f"Could not find config for '{alias}' in settings.STORAGES.")

        # Create a new storage instance using the retrieved parameters.
        storage = self.create_storage(params)
        # Assign the alias as the name to the created storage instance.
        storage.name = alias
        # Cache the newly created storage instance for future requests.
        self._storages[alias] = storage
        return storage

    def create_storage(self, params: dict[str, Any]) -> "Storage":
        """
        Creates and returns a new storage instance based on the provided parameters.
        This method dynamically loads the backend class and initializes it with
        the given options.

        Args:
            params (dict[str, Any]): A dictionary containing the configuration for
                                     the storage backend. It must include a "backend"
                                     key (string path to the storage class) and
                                     can optionally include an "options" key (dictionary
                                     of keyword arguments for the backend's constructor).

        Returns:
            "Storage": The newly created and initialized storage instance.

        Raises:
            InvalidStorageError: If the backend class specified in `params` cannot
                                 be imported (e.g., module not found, class not found).
        """
        # Get the backend string path and options from the parameters.
        backend = params.get("backend")
        options = params.get("options", {})

        try:
            # Dynamically load the storage class using `monkay.load`.
            storage_cls: type[Storage] = load(backend)
        except ImportError as e:
            # Raise an error if the backend class cannot be imported.
            raise InvalidStorageError(f"Could not find backend {backend!r}: {e}") from e
        # Instantiate the storage class with the provided options.
        return storage_cls(**options)
