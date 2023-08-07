import saffier
from my_project.utils import get_db_connection

_, registry = get_db_connection()


class User(saffier.Model):
    """
    Base model for a user
    """

    first_name = saffier.CharField(max_length=150)
    last_name = saffier.CharField(max_length=150)
    username = saffier.CharField(max_length=150, unique=True)
    email = saffier.EmailField(max_length=120, unique=True)
    password = saffier.CharField(max_length=128)
    last_login = saffier.DateTimeField(null=True)
    is_active = saffier.BooleanField(default=True)
    is_staff = saffier.BooleanField(default=False)
    is_superuser = saffier.BooleanField(default=False)

    class Meta:
        registry = registry
