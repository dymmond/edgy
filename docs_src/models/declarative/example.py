import saffier
from saffier import Database, Registry

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


# Declare the Saffier model


class User(saffier.Model):
    is_active = saffier.BooleanField(default=True)
    first_name = saffier.CharField(max_length=50)
    last_name = saffier.CharField(max_length=50)
    email = saffier.EmailField(max_lengh=100)
    password = saffier.CharField(max_length=1000)

    class Meta:
        registry = models


# Generate the declarative version
UserModelDeclarative = User.declarative()
