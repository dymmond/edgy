from typing import ClassVar

import edgy
from edgy import Manager, QuerySet


class InactiveManager(Manager):
    """
    Custom manager that will return only active users
    """

    def get_queryset(self) -> "QuerySet":
        queryset = super().get_queryset().filter(is_active=False)
        return queryset


class User(edgy.Model):
    # Add the new manager
    inactives: ClassVar[Manager] = InactiveManager()
