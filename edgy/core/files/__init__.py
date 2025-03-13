from typing import TYPE_CHECKING

from monkay import Monkay

if TYPE_CHECKING:
    from .base import ContentFile, FieldFile, File, ImageFieldFile
    from .storage import Storage, storages
Monkay(
    globals(),
    lazy_imports={
        "Storage": ".base.Storage",
        "storages": ".storage.storages",
        "ContentFile": ".base.ContentFile",
        "File": ".base.File",
        "FieldFile": ".base.FieldFile",
        "ImageFieldFile": ".base.ImageFieldFile",
    },
    uncached_imports={"storages"},
)

__all__ = ["File", "ContentFile", "FieldFile", "ImageFieldFile", "Storage", "storages"]
