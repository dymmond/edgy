import edgy
from edgy import Database, Registry

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


# Declare the Saffier model


class User(edgy.Model):
    is_active = edgy.BooleanField(default=True)
    first_name = edgy.CharField(max_length=50)
    last_name = edgy.CharField(max_length=50)
    email = edgy.EmailField(max_lengh=100)
    password = edgy.CharField(max_length=1000)

    class Meta:
        registry = models


# Generate the declarative version
UserModelDeclarative = User.declarative()
