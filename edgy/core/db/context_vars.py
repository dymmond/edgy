from __future__ import annotations

from collections.abc import Generator, Iterable
from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import TYPE_CHECKING, Literal, cast
from warnings import warn

if TYPE_CHECKING:
    from edgy.core.connection.registry import Registry
    from edgy.core.db.fields.types import FIELD_CONTEXT_TYPE
    from edgy.core.db.models.types import BaseModelType
    from edgy.core.db.querysets.base import QuerySet

# A frozen set used as a default empty set for context variables, preventing modification.
_empty: set = cast(set, frozenset())

# Context variable to hold a fallback target registry. This is used when a specific
# registry is not explicitly provided, allowing Edgy to locate models across different
# registries or during specific operations that require a default registry.
FALLBACK_TARGET_REGISTRY: ContextVar[Registry | None] = ContextVar(
    "FALLBACK_TARGET_REGISTRY", default=None
)

# Context variable to force specific fields to be nullable, typically used during
# schema generation or database migrations to temporarily override field constraints.
# It stores a set of tuples, where each tuple contains (model_name, field_name).
FORCE_FIELDS_NULLABLE: ContextVar[set[tuple[str, str]]] = ContextVar(
    "FORCE_FIELDS_NULLABLE", default=_empty
)

# Context variable to store the current field context being processed. This is
# crucial for operations like field validation, serialization, or deserialization,
# where the context of the field (e.g., whether it's part of a create or update operation)
# influences its behavior.
CURRENT_FIELD_CONTEXT: ContextVar[FIELD_CONTEXT_TYPE] = ContextVar("CURRENT_FIELD_CONTEXT")

# Context variable to hold the currently active model instance or QuerySet.
# This is used for operations that need to know the context of the current model
# or queryset, such as during relationship loading or method calls that operate
# on the current object.
CURRENT_INSTANCE: ContextVar[BaseModelType | QuerySet | None] = ContextVar(
    "CURRENT_INSTANCE", default=None
)

# Context variable specifically for the currently active BaseModelType instance.
# This differentiates from CURRENT_INSTANCE by strictly holding a BaseModelType,
# which is useful for operations directly related to a model's lifecycle.
CURRENT_MODEL_INSTANCE: ContextVar[BaseModelType | None] = ContextVar(
    "CURRENT_MODEL_INSTANCE", default=None
)

# Context variable to indicate the current phase of an operation (e.g., "loading", "saving").
# This allows for phase-specific logic or validations to be applied.
CURRENT_PHASE: ContextVar[str] = ContextVar("CURRENT_PHASE", default="")

# Context variable to globally disable field constraints. When set to True,
# it can bypass certain field-level validations or requirements, often used
# for specific internal operations or data migrations.
NO_GLOBAL_FIELD_CONSTRAINTS: ContextVar[bool] = ContextVar(
    "NO_GLOBAL_FIELD_CONSTRAINTS", default=False
)

# Context variable to hold a set of explicitly specified values during model operations.
# This helps in distinguishing between fields that were explicitly provided by the user
# versus those that might have default values or were omitted.
EXPLICIT_SPECIFIED_VALUES: ContextVar[set[str] | None] = ContextVar(
    "EXPLICIT_SPECIFIED_VALUES", default=None
)

# Context variable controlling the behavior of model's __getattr__ method for lazy loading.
# "passdown": Attribute access is passed down without loading.
# "load": Attribute is eagerly loaded.
# "coro": Attribute loading returns a coroutine.
MODEL_GETATTR_BEHAVIOR: ContextVar[Literal["passdown", "load", "coro"]] = ContextVar(
    "MODEL_GETATTR_BEHAVIOR", default="load"
)

# Context variable to store the current tenant. This is used in multi-tenant
# environments to scope database operations to a specific tenant's data.
# Defaults to None, indicating no specific tenant is active.
TENANT: ContextVar[str | None] = ContextVar("tenant", default=None)

# Context variable to store the current database schema. In environments
# where database schemas are used for logical separation (e.g., multi-tenancy),
# this variable specifies which schema subsequent operations should target.
# Defaults to None.
SCHEMA: ContextVar[str | None] = ContextVar("SCHEMA", default=None)

# Backward compatibility alias for SCHEMA.
SHEMA = SCHEMA


def get_tenant() -> str | None:
    """
    Retrieves the current active tenant from the context.

    Returns:
        str | None: The name of the current tenant, or None if no tenant is set.
    """
    return TENANT.get()


def set_tenant(value: str | None) -> Token:
    """
    Sets the global tenant for the context of subsequent queries and operations.
    When a global tenant is set, the `get_schema` method will ignore the `SCHEMA`
    context variable and return the tenant value instead.

    This function is deprecated due to potential issues with scope management
    and its interaction with `SCHEMA`. It is recommended to use `with_tenant`
    for safer, scoped tenant management.

    Args:
        value (str | None): The tenant name to set, or None to clear the tenant.

    Returns:
        Token: A token that can be used to reset the context variable to its
               previous value.

    Warns:
        DeprecationWarning: Always warns about deprecation and recommends `with_tenant`.
    """
    warn(
        "`set_tenant` is deprecated; use `with_tenant` instead. WARNING: this function "
        "is broken and doesn't reset the tenant.",
        DeprecationWarning,
        stacklevel=2,
    )
    # The reason for deprecating this is that it directly overwrites the schema
    # context and can lead to hard-to-debug issues if the scope isn't properly
    # managed or reset, unlike `with_tenant` which provides a limited scope.
    return TENANT.set(value)


@contextmanager
def with_tenant(tenant: str | None) -> Generator[None, None, None]:
    """
    A context manager that sets the global tenant for the duration of its block.
    When inside this context, subsequent queries and operations will be scoped
    to the specified tenant. This approach is preferred over `set_tenant` as
    it ensures the tenant context is properly reset upon exiting the block,
    preventing unintended side effects.

    When a global tenant is set via this context manager, the `get_schema`
    method will ignore the `SCHEMA` context variable and return the tenant value.

    Args:
        tenant (str | None): The tenant name to set, or None to clear the tenant
                             within this context.

    Yields:
        None: The execution context within which the tenant is active.
    """
    # This context manager is preferred over `set_tenant` because `set_tenant`
    # overwrites the schema context globally and can cause difficult-to-debug
    # issues if the scope is not reset. This context manager provides a
    # limited scope, ensuring the context is properly managed.
    # Note: `set_tenant` (the deprecated function) affects the `get_schema` method.
    token = TENANT.set(tenant)
    try:
        yield
    finally:
        TENANT.reset(token)


def _process_force_field_nullable(item: str | tuple[str, str]) -> tuple[str, str]:
    """
    Internal helper function to process an item into a standardized tuple format
    for `FORCE_FIELDS_NULLABLE`.

    Args:
        item (str | tuple[str, str]): The item to process. Can be a string in
                                      "model_name:field_name" format or a
                                      pre-formatted tuple.

    Returns:
        tuple[str, str]: A tuple containing (model_name, field_name).

    Raises:
        AssertionError: If the processed result is not a tuple of two strings.
    """
    result = item if isinstance(item, tuple) else tuple(item.split(":"))
    # Assertions to ensure the result is in the expected format.
    assert isinstance(result, tuple) and len(result) == 2
    assert isinstance(result[0], str)
    assert isinstance(result[1], str)
    return result


@contextmanager
def with_force_fields_nullable(
    inp: Iterable[str | tuple[str, str]],
) -> Generator[None, None, None]:
    """
    A context manager that temporarily forces specified fields to be nullable.
    This is typically used during schema operations or migrations where field
    nullability needs to be overridden without altering the model definition.

    Args:
        inp (Iterable[str | tuple[str, str]]): An iterable of field identifiers.
                                                Each identifier can be a string
                                                in the format "model_name:field_name"
                                                or a tuple (model_name, field_name).

    Yields:
        None: The execution context within which the fields are forced nullable.
    """
    # Set the FORCE_FIELDS_NULLABLE context variable with the processed input.
    token = FORCE_FIELDS_NULLABLE.set({_process_force_field_nullable(item) for item in inp})
    try:
        yield
    finally:
        # Reset the context variable to its previous state upon exiting the block.
        FORCE_FIELDS_NULLABLE.reset(token)


def get_schema(check_tenant: bool = True) -> str | None:
    """
    Retrieves the current active database schema from the context.
    If `check_tenant` is True and a tenant is set, the tenant name
    will be returned as the schema, overriding the `SCHEMA` context variable.

    Args:
        check_tenant (bool): If True, checks for an active tenant first and
                             returns it as the schema if present. Defaults to True.

    Returns:
        str | None: The name of the current schema or tenant, or None if neither is set.
    """
    if check_tenant:
        tenant = get_tenant()
        if tenant is not None:
            return tenant
    return SCHEMA.get()


def set_schema(value: str | None) -> Token:
    """
    Sets the current database schema and returns a `Token` that can be used
    to reset the schema context to its previous value. This is a manual way
    to manage schema context, typically used when `with_schema` is not suitable.

    Args:
        value (str | None): The schema name to set, or None to clear the schema.

    Returns:
        Token: A token for resetting the schema context.
    """
    return SCHEMA.set(value)


@contextmanager
def with_schema(schema: str | None) -> Generator[None, None, None]:
    """
    A context manager that sets the current database schema for the duration
    of its block. Upon exiting the block, the schema context is automatically
    reset to its previous value. This provides a safe and scoped way to
    manage schema changes for database operations.

    Args:
        schema (str | None): The schema name to set, or None to clear the schema
                             within this context.

    Yields:
        None: The execution context within which the schema is active.
    """
    token = SCHEMA.set(schema)
    try:
        yield
    finally:
        SCHEMA.reset(token)
