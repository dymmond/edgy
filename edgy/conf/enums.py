from enum import Enum


class EnvironmentType(str, Enum):
    """An Enum for HTTP methods."""

    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"
