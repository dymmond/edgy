from enum import Enum
from warnings import warn

warn(
    "This module is deprecated. Use `esmerald.conf.EnvironmentType` instead when using Esmerald "
    "or define otherwise your own EnvironmentType.",
    DeprecationWarning,
    stacklevel=2,
)


class EnvironmentType(str, Enum):
    """An Enum for environments."""

    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"
