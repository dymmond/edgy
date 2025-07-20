from enum import Enum
from warnings import warn

warn(
    "This module is deprecated. Use `esmerald.conf.EnvironmentType` instead when using Esmerald "
    "or define otherwise your own EnvironmentType.",
    DeprecationWarning,
    stacklevel=2,
)


class EnvironmentType(str, Enum):
    """
    An enumeration representing different types of application environments.

    This Enum provides standardized environment types that can be used to
    configure application behavior based on whether it's in development,
    testing, or production.
    """

    DEVELOPMENT = "development"
    """
    Represents the development environment.

    In this environment, features like debugging, detailed logging,
    and hot-reloading are typically enabled.
    """
    TESTING = "testing"
    """
    Represents the testing environment.

    This environment is used for running automated tests, often with a
    dedicated test database and specific configurations for test execution.
    """
    PRODUCTION = "production"
    """
    Represents the production environment.

    This is the live environment where the application is deployed for end-users.
    Configurations here prioritize performance, security, and stability,
    with minimal debugging information exposed.
    """
