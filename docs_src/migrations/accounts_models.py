from datetime import datetime

from my_project.utils import get_db_connection

import edgy

registry = get_db_connection()


class User(edgy.Model):
    """
    Base model for a user
    """

    first_name: str = edgy.CharField(max_length=150)
    last_name: str = edgy.CharField(max_length=150)
    username: str = edgy.CharField(max_length=150, unique=True)
    email: str = edgy.EmailField(max_length=120, unique=True)
    password: str = edgy.CharField(max_length=128)
    last_login: datetime = edgy.DateTimeField(null=True)
    is_active: bool = edgy.BooleanField(default=True)
    is_staff: bool = edgy.BooleanField(default=False)
    is_superuser: bool = edgy.BooleanField(default=False)

    class Meta:
        registry = registry
