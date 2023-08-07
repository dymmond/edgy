import edgy
from edgy import Database, Registry

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


# Declare the Edgy model


class User(edgy.Model):
    is_active: bool = edgy.BooleanField(default=True)
    first_name: str = edgy.CharField(max_length=50)
    last_name: str = edgy.CharField(max_length=50)
    email: str = edgy.EmailField(max_lengh=100)
    password: str = edgy.CharField(max_length=1000)

    class Meta:
        registry = models


# Generate the declarative version
UserModelDeclarative = User.declarative()
