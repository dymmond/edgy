from __future__ import annotations

from contextvars import ContextVar
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .types import ModelFactoryContext

model_factory_context: ContextVar[ModelFactoryContext] = ContextVar("model_factory_context")
