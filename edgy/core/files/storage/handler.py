from functools import cached_property
from typing import TYPE_CHECKING, Any, Union

from edgy.conf import settings
from edgy.conf.module_import import import_string
from edgy.exceptions import InvalidStorageError

if TYPE_CHECKING:
    from edgy.core.files.storage.base import Storage


class StorageHandler:
    """
    The handler for the available storages
    of the system.
    """

    def __init__(self, backends: Union[dict[str, Any], None] = None) -> None:
        self._backends = backends
        self._storages: dict[str, Storage] = {}

    @cached_property
    def backends(self) -> dict[str, Any]:
        if self._backends is None:
            self._backends = settings.storages.copy()
        return self._backends

    def __getitem__(self, alias: str) -> "Storage":
        """
        Get the storage instance associated with the given alias.

        Args:
            alias (str): The alias of the storage.

        Returns:
            storage: The storage instance.

        Raises:
            InvalidStorageError: If the alias is not found in settings.STORAGES.
        """
        storage = self._storages.get(alias, None)
        if storage is not None:
            return storage

        params = self.backends.get(alias, None)
        if params is None:
            raise InvalidStorageError(f"Could not find config for '{alias}' in settings.STORAGES.")

        storage = self.create_storage(params)
        storage.name = alias
        self._storages[alias] = storage
        return storage

    def create_storage(self, params: dict[str, Any]) -> "Storage":
        """
        Create a storage instance based on the provided parameters.

        Args:
            params (dict): The parameters for configuring the storage.

        Returns:
            storage: The storage instance.

        Raises:
            InvalidStorageError: If the backend specified in params cannot be imported.
        """
        backend = params.pop("backend")
        options = params.pop("options", {})

        try:
            storage_cls: type[Storage] = import_string(backend)
        except ImportError as e:
            raise InvalidStorageError(f"Could not find backend {backend!r}: {e}") from e
        return storage_cls(**options)
