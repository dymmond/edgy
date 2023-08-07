from my_project.utils import get_db_connection

import edgy

_, registry = get_db_connection()


class User(edgy.Model):
    """
    Base model for a user
    """

    first_name = edgy.CharField(max_length=150)
    last_name = edgy.CharField(max_length=150)
    username = edgy.CharField(max_length=150, unique=True)
    email = edgy.EmailField(max_length=120, unique=True)
    password = edgy.CharField(max_length=128)
    last_login = edgy.DateTimeField(null=True)
    is_active = edgy.BooleanField(default=True)
    is_staff = edgy.BooleanField(default=False)
    is_superuser = edgy.BooleanField(default=False)

    class Meta:
        registry = registry
