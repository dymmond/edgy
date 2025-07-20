from __future__ import annotations

from contextvars import ContextVar
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .types import ModelFactoryContext

# Define a ContextVar to hold the current ModelFactoryContext.
# This allows factory calls to access a shared, thread-local context,
# which is crucial for managing recursive factory calls, Faker instances,
# and other shared state across nested factory generations.
model_factory_context: ContextVar[ModelFactoryContext] = ContextVar("model_factory_context")
