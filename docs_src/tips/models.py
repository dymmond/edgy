from enum import Enum

from my_project.utils import get_db_connection

import edgy

_, registry = get_db_connection()


class ProfileChoice(Enum):
    ADMIN = "ADMIN"
    USER = "USER"


class BaseModel(edgy.Model):
    class Meta:
        abstract = True
        registry = registry


class User(BaseModel):
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


class Profile(BaseModel):
    """
    A profile for a given user.
    """

    user = edgy.OneToOneField(User, on_delete=edgy.CASCADE)
    profile_type = edgy.ChoiceField(ProfileChoice, default=ProfileChoice.USER)
