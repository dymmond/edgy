from .base import Storage
from .handler import StorageHandler

storages = StorageHandler()

__all__ = ["Storage", "StorageHandler", "storages"]
