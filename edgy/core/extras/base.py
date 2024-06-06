from abc import ABC, abstractmethod
from typing import Any


class BaseExtra(ABC):
    @abstractmethod
    def set_edgy_extension(self, app: Any, **kwargs: Any) -> None:
        raise NotImplementedError("Any class implementing the extra must implement set_edgy_extension() .")
