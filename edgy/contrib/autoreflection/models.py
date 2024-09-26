from typing import ClassVar

import edgy

from .metaclasses import AutoReflectionMeta, AutoReflectionMetaInfo


class AutoReflectModel(edgy.ReflectModel, metaclass=AutoReflectionMeta):
    meta: ClassVar[AutoReflectionMetaInfo]
